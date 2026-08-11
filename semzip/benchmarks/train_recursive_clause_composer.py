from __future__ import annotations

import argparse
from collections import defaultdict
import json
import random
import re
from pathlib import Path

from compiler_composition_clean_corpus import generate_clean_composition_examples
from compiler_delta_corpus import MAX_SLOTS, NONE_SLOT, RELATIONS, DeltaExample

RELATION_COUNT = len(RELATIONS)
SUBSET_COUNT = 1 << RELATION_COUNT


def batches(items, size, rng):
    idx = list(range(len(items))); rng.shuffle(idx)
    for start in range(0, len(idx), size):
        yield [items[i] for i in idx[start:start + size]]


def split_clauses(text: str) -> tuple[str, ...]:
    """Deterministic baseline segmenter for the clean composition experiment."""
    pieces = tuple(piece.strip() for piece in re.split(r"(?<=[.!?])\s+", text.strip()) if piece.strip())
    return pieces or (text.strip(),)


def marker_spans(text):
    out = {}
    for slot in range(MAX_SLOTS):
        m = re.search(rf"(?<![A-Za-z0-9_])E{slot}(?![A-Za-z0-9_])", text)
        if m: out[slot] = m.span()
    return out


def atomic_targets(example: DeltaExample):
    masks = [0] * MAX_SLOTS
    source = [[NONE_SLOT] * RELATION_COUNT for _ in range(MAX_SLOTS)]
    destination = [[NONE_SLOT] * RELATION_COUNT for _ in range(MAX_SLOTS)]

    def add(subject, src, dst, bits):
        if subject == NONE_SLOT: return
        for r, enabled in enumerate(bits):
            if enabled:
                masks[subject] |= 1 << r
                source[subject][r] = src
                destination[subject][r] = dst

    f = example.frame
    add(f.primary_subject, f.primary_source, f.primary_destination, f.primary_relations)
    if f.secondary_present:
        add(f.secondary_subject, f.secondary_source, f.secondary_destination, f.secondary_relations)
    return masks, source, destination


def merged_gold(example: DeltaExample):
    return atomic_targets(example)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="google/bert_uncased_L-2_H-128_A-2")
    ap.add_argument("--train-samples", type=int, default=512)
    ap.add_argument("--eval-samples", type=int, default=96)
    ap.add_argument("--epochs", type=int, default=14)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--backbone-lr", type=float, default=5e-5)
    ap.add_argument("--head-lr", type=float, default=5e-4)
    ap.add_argument("--semantic-dim", type=int, default=32)
    ap.add_argument("--seed", type=int, default=61)
    args = ap.parse_args()

    import torch
    import torch.nn as nn
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed); random.seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    train = generate_clean_composition_examples(args.train_samples, split="train", seed=23)
    evaluation = generate_clean_composition_examples(args.eval_samples, split="eval", seed=24)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    backbone = AutoModel.from_pretrained(args.model)
    hidden = int(backbone.config.hidden_size); d = args.semantic_dim

    class AtomicCompiler(nn.Module):
        def __init__(self):
            super().__init__(); self.backbone = backbone
            self.entity_projection = nn.Linear(hidden, d, bias=False)
            self.global_projection = nn.Linear(hidden, d, bias=False)
            self.mask_head = nn.Linear(d, SUBSET_COUNT)
            self.relation_embedding = nn.Parameter(torch.empty(RELATION_COUNT, d))
            nn.init.normal_(self.relation_embedding, std=d ** -0.5)
            self.source_query = nn.Linear(d, d, bias=False)
            self.destination_query = nn.Linear(d, d, bias=False)
            self.source_none = nn.Linear(d, 1)
            self.destination_none = nn.Linear(d, 1)

        def forward(self, input_ids, attention_mask, positions, present, token_type_ids=None):
            kw={"input_ids":input_ids,"attention_mask":attention_mask}
            if token_type_ids is not None: kw["token_type_ids"]=token_type_ids
            states=self.backbone(**kw).last_hidden_state; pooled=states[:,0]; b=states.shape[0]
            ep=positions.clamp_min(0); entity_states=states[torch.arange(b).unsqueeze(1),ep]
            entity=self.entity_projection(entity_states); global_state=self.global_projection(pooled)[:,None,:]
            subject=torch.tanh(entity+global_state); mask_logits=self.mask_head(subject)
            mask_logits=mask_logits.masked_fill(~present[:,:,None],-1e9)
            mask_logits[:,:,0]=torch.where(present,mask_logits[:,:,0],torch.zeros_like(mask_logits[:,:,0]))
            cells=torch.tanh(subject[:,:,None,:]+self.relation_embedding[None,None,:,:]); keys=entity
            sq=self.source_query(cells); dq=self.destination_query(cells)
            src=torch.einsum("bsrd,btd->bsrt",sq,keys)/(d**.5); dst=torch.einsum("bsrd,btd->bsrt",dq,keys)/(d**.5)
            src=src.masked_fill(~present[:,None,None,:],-1e9); dst=dst.masked_fill(~present[:,None,None,:],-1e9)
            src=torch.cat((src,self.source_none(cells)),dim=-1); dst=torch.cat((dst,self.destination_none(cells)),dim=-1)
            return mask_logits,src,dst

    model=AtomicCompiler(); total=sum(p.numel() for p in model.parameters()); backbone_n=sum(p.numel() for p in model.backbone.parameters())
    head_params=[p for n,p in model.named_parameters() if not n.startswith("backbone.")]
    opt=torch.optim.AdamW([{"params":model.backbone.parameters(),"lr":args.backbone_lr},{"params":head_params,"lr":args.head_lr}],weight_decay=.01)
    ce=nn.CrossEntropyLoss(); rng=random.Random(args.seed)

    def encode_texts(texts):
        enc=tokenizer(texts,padding=True,truncation=True,max_length=96,return_tensors="pt",return_offsets_mapping=True)
        offsets=enc.pop("offset_mapping"); pos=torch.full((len(texts),MAX_SLOTS),-1,dtype=torch.long); present=torch.zeros((len(texts),MAX_SLOTS),dtype=torch.bool)
        for row,text in enumerate(texts):
            for slot,(cs,ce_) in marker_spans(text).items():
                for ti,(s,e) in enumerate(offsets[row].tolist()):
                    if s<ce_ and e>cs: pos[row,slot]=ti; present[row,slot]=True; break
        return enc,pos,present

    def encode_examples(group):
        texts=[x.text for x in group]; enc,pos,present=encode_texts(texts); ts=[atomic_targets(x) for x in group]
        return enc,pos,present,torch.tensor([x[0] for x in ts]),torch.tensor([x[1] for x in ts]),torch.tensor([x[2] for x in ts])

    history=[]; model.train()
    for epoch in range(args.epochs):
        tot=seen=0
        for group in batches(train,args.batch_size,rng):
            enc,pos,present,masks,src,dst=encode_examples(group); opt.zero_grad(set_to_none=True)
            ml,sl,dl=model(enc["input_ids"],enc["attention_mask"],pos,present,enc.get("token_type_ids"))
            loss=ce(ml[present],masks[present]); active=torch.zeros_like(src,dtype=torch.bool)
            for r in range(RELATION_COUNT): active[:,:,r]=((masks>>r)&1).bool()
            if bool(active.any()): loss=loss+ce(sl[active],src[active])+ce(dl[active],dst[active])
            loss.backward(); opt.step(); tot+=float(loss.detach())*len(group); seen+=len(group)
        avg=tot/seen; history.append(avg); print(f"epoch={epoch+1} average_loss={avg:.6f}")

    def predict_clause(clause: str):
        enc,pos,present=encode_texts([clause]); ml,sl,dl=model(enc["input_ids"],enc["attention_mask"],pos,present,enc.get("token_type_ids"))
        masks=ml.argmax(-1)[0]; src=sl.argmax(-1)[0]; dst=dl.argmax(-1)[0]; masks[~present[0]]=0
        # Decode only active relation cells.
        effect={}
        for s in range(MAX_SLOTS):
            for r in range(RELATION_COUNT):
                if (int(masks[s])>>r)&1:
                    effect[(s,r)]=(int(src[s,r]),int(dst[s,r]))
        return effect

    exact=0; family=defaultdict(lambda:{"exact":0,"total":0}); conflict_count=0; clause_count=0; mistakes=[]; model.eval()
    with torch.no_grad():
        for ex in evaluation:
            merged={}; conflict=False; clauses=split_clauses(ex.text); clause_count+=len(clauses)
            for clause in clauses:
                effect=predict_clause(clause)
                for key,value in effect.items():
                    previous=merged.get(key)
                    if previous is not None and previous!=value: conflict=True
                    else: merged[key]=value
            if conflict: conflict_count+=1
            gm,gs,gd=merged_gold(ex); gold={}
            for s in range(MAX_SLOTS):
                for r in range(RELATION_COUNT):
                    if (int(gm[s])>>r)&1: gold[(s,r)]=(int(gs[s][r]),int(gd[s][r]))
            ok=(not conflict and merged==gold); exact+=int(ok); family[ex.family]["exact"]+=int(ok); family[ex.family]["total"]+=1
            if not ok and len(mistakes)<24: mistakes.append({"text":ex.text,"clauses":list(clauses),"gold":repr(gold),"predicted":repr(merged),"conflict":conflict})

    report={"model":args.model,"mode":"recursive_atomic_clause_to_patch_union","total_parameters":total,"backbone_parameters":backbone_n,"head_parameters":total-backbone_n,"train_samples":len(train),"eval_samples":len(evaluation),"epochs":args.epochs,"mean_clauses_per_eval":clause_count/len(evaluation),"composition_conflicts":conflict_count,"exact_patch":exact,"exact_patch_accuracy":exact/len(evaluation),"family_exact":dict(family),"loss_history":history,"mistakes":mistakes,"contract":{"atomic_compiler_only":True,"composition_is_deterministic_union":True,"segmenter_is_deterministic_baseline":True,"unseen_relation_conjunction_in_neural_forward_pass":False}}
    Path("compiler-recursive-clause-results.json").write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ("model","mode","total_parameters","head_parameters","mean_clauses_per_eval","composition_conflicts","exact_patch","exact_patch_accuracy","family_exact","loss_history")},indent=2))

if __name__=="__main__": main()

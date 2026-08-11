from __future__ import annotations

import argparse
from collections import defaultdict
import json
import random
import re
from pathlib import Path

from compiler_delta_corpus import MAX_SLOTS, NONE_SLOT, RELATIONS, DeltaExample, generate_delta_examples

RELATION_COUNT = len(RELATIONS)


def batches(items, size, rng):
    idx = list(range(len(items))); rng.shuffle(idx)
    for start in range(0, len(idx), size):
        yield [items[i] for i in idx[start:start + size]]


def marker_spans(text):
    out = {}
    for slot in range(MAX_SLOTS):
        m = re.search(rf"(?<![A-Za-z0-9_])E{slot}(?![A-Za-z0-9_])", text)
        if m: out[slot] = m.span()
    return out


def targets(example: DeltaExample):
    src = [[NONE_SLOT] * RELATION_COUNT for _ in range(MAX_SLOTS)]
    dst = [[NONE_SLOT] * RELATION_COUNT for _ in range(MAX_SLOTS)]
    def add(subject, source, destination, bits):
        if subject == NONE_SLOT: return
        for relation, enabled in enumerate(bits):
            if enabled:
                if src[subject][relation] != NONE_SLOT:
                    raise ValueError("duplicate subject/relation transition")
                src[subject][relation] = source
                dst[subject][relation] = destination
    f = example.frame
    add(f.primary_subject, f.primary_source, f.primary_destination, f.primary_relations)
    if f.secondary_present:
        add(f.secondary_subject, f.secondary_source, f.secondary_destination, f.secondary_relations)
    obligation_active = int(f.return_obligation)
    obligation = ((f.primary_subject, f.primary_destination, f.primary_source)
                  if obligation_active else (NONE_SLOT, NONE_SLOT, NONE_SLOT))
    return src, dst, obligation_active, obligation


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
    ap.add_argument("--none-weight", type=float, default=0.35)
    ap.add_argument("--seed", type=int, default=47)
    args = ap.parse_args()

    import torch
    import torch.nn as nn
    from transformers import AutoModel, AutoTokenizer
    torch.manual_seed(args.seed); random.seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))

    train = generate_delta_examples(args.train_samples, split="train", seed=23)
    evaluation = generate_delta_examples(args.eval_samples, split="eval", seed=24)
    tok = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    backbone = AutoModel.from_pretrained(args.model)
    hidden = int(backbone.config.hidden_size); d = args.semantic_dim

    class Model(nn.Module):
        def __init__(self):
            super().__init__(); self.backbone = backbone
            self.entity_key = nn.Linear(hidden, d, bias=False)
            self.entity_subject = nn.Linear(hidden, d, bias=False)
            self.global_projection = nn.Linear(hidden, d, bias=False)
            self.relation_embedding = nn.Parameter(torch.empty(RELATION_COUNT, d))
            nn.init.normal_(self.relation_embedding, std=d ** -0.5)
            self.source_query = nn.Linear(d, d, bias=False)
            self.destination_query = nn.Linear(d, d, bias=False)
            self.source_none = nn.Linear(d, 1)
            self.destination_none = nn.Linear(d, 1)
            self.obligation_active = nn.Linear(hidden, 1)
            self.obligation_queries = nn.Linear(hidden, 3 * d)
            self.obligation_none = nn.Linear(hidden, 3)

        def pointer(self, query, keys, present, none):
            scores = torch.einsum("bsrd,btd->bsrt", query, keys) / (d ** .5)
            scores = scores.masked_fill(~present[:, None, None, :], -1e9)
            return torch.cat((scores, none), dim=-1)

        def forward(self, input_ids, attention_mask, positions, present, token_type_ids=None):
            kw = {"input_ids": input_ids, "attention_mask": attention_mask}
            if token_type_ids is not None: kw["token_type_ids"] = token_type_ids
            states = self.backbone(**kw).last_hidden_state; pooled = states[:,0]
            b = states.shape[0]; ep = positions.clamp_min(0)
            entity_states = states[torch.arange(b).unsqueeze(1), ep]
            keys = self.entity_key(entity_states)
            cell = torch.tanh(self.entity_subject(entity_states)[:,:,None,:] +
                              self.global_projection(pooled)[:,None,None,:] +
                              self.relation_embedding[None,None,:,:])
            src = self.pointer(self.source_query(cell), keys, present, self.source_none(cell))
            dst = self.pointer(self.destination_query(cell), keys, present, self.destination_none(cell))
            oa = self.obligation_active(pooled).squeeze(-1)
            oq = self.obligation_queries(pooled).view(b,3,d)
            op = torch.einsum("brd,bsd->brs", oq, keys) / (d ** .5)
            op = op.masked_fill(~present[:,None,:], -1e9)
            op = torch.cat((op, self.obligation_none(pooled).unsqueeze(-1)), dim=-1)
            return src, dst, oa, op

    model = Model(); total = sum(p.numel() for p in model.parameters())
    backbone_n = sum(p.numel() for p in model.backbone.parameters()); head_n = total-backbone_n
    head_params = [p for n,p in model.named_parameters() if not n.startswith("backbone.")]
    opt = torch.optim.AdamW([{"params":model.backbone.parameters(),"lr":args.backbone_lr},
                             {"params":head_params,"lr":args.head_lr}], weight_decay=.01)
    weights = torch.ones(MAX_SLOTS+1); weights[NONE_SLOT] = args.none_weight
    ce = nn.CrossEntropyLoss(weight=weights)
    bce = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(3.0)); rng = random.Random(args.seed)

    def encode(group):
        texts=[x.text for x in group]
        enc=tok(texts,padding=True,truncation=True,max_length=96,return_tensors="pt",return_offsets_mapping=True)
        offsets=enc.pop("offset_mapping")
        pos=torch.full((len(group),MAX_SLOTS),-1,dtype=torch.long); present=torch.zeros((len(group),MAX_SLOTS),dtype=torch.bool)
        for row,text in enumerate(texts):
            for slot,(cs,ce_) in marker_spans(text).items():
                for ti,(s,e) in enumerate(offsets[row].tolist()):
                    if s < ce_ and e > cs: pos[row,slot]=ti; present[row,slot]=True; break
        ts=[targets(x) for x in group]
        return enc,pos,present,torch.tensor([x[0] for x in ts]),torch.tensor([x[1] for x in ts]),torch.tensor([x[2] for x in ts],dtype=torch.float32),torch.tensor([x[3] for x in ts])

    history=[]; model.train()
    for epoch in range(args.epochs):
        tot=seen=0
        for group in batches(train,args.batch_size,rng):
            enc,pos,present,src,dst,oa,optr=encode(group); opt.zero_grad(set_to_none=True)
            sl,dl,oal,opl=model(enc["input_ids"],enc["attention_mask"],pos,present,enc.get("token_type_ids"))
            cellmask=present[:,:,None].expand(-1,-1,RELATION_COUNT)
            loss=ce(sl[cellmask],src[cellmask])+ce(dl[cellmask],dst[cellmask])+bce(oal,oa)
            om=oa>.5
            if bool(om.any()):
                for r in range(3): loss=loss+ce(opl[om,r],optr[om,r])
            loss.backward(); opt.step(); tot+=float(loss.detach())*len(group); seen+=len(group)
        avg=tot/seen; history.append(avg); print(f"epoch={epoch+1} average_loss={avg:.6f}")

    exact=ptr_correct=ptr_total=active_detect_correct=active_detect_total=0
    fam=defaultdict(lambda:{"exact":0,"total":0}); mistakes=[]; model.eval()
    with torch.no_grad():
        for start in range(0,len(evaluation),args.batch_size):
            group=list(evaluation[start:start+args.batch_size]); enc,pos,present,src,dst,oa,optr=encode(group)
            sl,dl,oal,opl=model(enc["input_ids"],enc["attention_mask"],pos,present,enc.get("token_type_ids"))
            ps=sl.argmax(-1); pd=dl.argmax(-1); poa=(oal.sigmoid()>=.5).long(); pop=opl.argmax(-1)
            for row,ex in enumerate(group):
                ps[row,~present[row],:]=NONE_SLOT; pd[row,~present[row],:]=NONE_SLOT
                gold_active=(src[row]!=NONE_SLOT)|(dst[row]!=NONE_SLOT); pred_active=(ps[row]!=NONE_SLOT)|(pd[row]!=NONE_SLOT)
                active_detect_correct+=int((gold_active==pred_active).sum()); active_detect_total+=gold_active.numel()
                ptr_correct+=int((ps[row]==src[row]).sum())+int((pd[row]==dst[row]).sum()); ptr_total+=2*src[row].numel()
                cop=pop[row].clone()
                if int(poa[row])==0: cop[:]=NONE_SLOT
                ok=(torch.equal(ps[row],src[row]) and torch.equal(pd[row],dst[row]) and int(poa[row])==int(oa[row]) and torch.equal(cop,optr[row]))
                exact+=int(ok); fam[ex.family]["exact"]+=int(ok); fam[ex.family]["total"]+=1
                if not ok and len(mistakes)<24: mistakes.append({"text":ex.text,"family":ex.family,"gold_source":src[row].tolist(),"predicted_source":ps[row].tolist(),"gold_destination":dst[row].tolist(),"predicted_destination":pd[row].tolist(),"gold_obligation":int(oa[row]),"predicted_obligation":int(poa[row]),"slots":list(ex.slots)})

    report={"model":args.model,"mode":"pointer_only_relation_grid","none_weight":args.none_weight,"total_parameters":total,"backbone_parameters":backbone_n,"head_parameters":head_n,"train_samples":len(train),"eval_samples":len(evaluation),"epochs":args.epochs,"cell_activity_accuracy":active_detect_correct/active_detect_total,"all_pointer_accuracy":ptr_correct/ptr_total,"exact_frame":exact,"exact_frame_accuracy":exact/len(evaluation),"family_exact":dict(fam),"loss_history":history,"mistakes":mistakes,"contract":{"event_classes":False,"primary_secondary_order":False,"active_bit":False,"none_none_means_no_change":True}}
    Path("compiler-relation-pointer-grid-results.json").write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ("model","mode","none_weight","total_parameters","head_parameters","cell_activity_accuracy","all_pointer_accuracy","exact_frame","exact_frame_accuracy","family_exact","loss_history")},indent=2))

if __name__=="__main__": main()

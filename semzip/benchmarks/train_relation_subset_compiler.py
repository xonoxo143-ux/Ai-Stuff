from __future__ import annotations

import argparse
from collections import defaultdict
import json
import random
import re
from pathlib import Path

from compiler_delta_corpus import MAX_SLOTS, NONE_SLOT, RELATIONS, DeltaExample, generate_delta_examples

RELATION_COUNT = len(RELATIONS)
SUBSET_COUNT = 1 << RELATION_COUNT


def batches(items, size, rng):
    indices = list(range(len(items)))
    rng.shuffle(indices)
    for start in range(0, len(indices), size):
        yield [items[i] for i in indices[start:start + size]]


def marker_spans(text: str):
    spans = {}
    for slot in range(MAX_SLOTS):
        match = re.search(rf"(?<![A-Za-z0-9_])E{slot}(?![A-Za-z0-9_])", text)
        if match:
            spans[slot] = match.span()
    return spans


def targets(example: DeltaExample):
    masks = [0] * MAX_SLOTS
    source = [[NONE_SLOT] * RELATION_COUNT for _ in range(MAX_SLOTS)]
    destination = [[NONE_SLOT] * RELATION_COUNT for _ in range(MAX_SLOTS)]

    def add(subject, src, dst, bits):
        if subject == NONE_SLOT:
            return
        for relation, enabled in enumerate(bits):
            if enabled:
                masks[subject] |= 1 << relation
                source[subject][relation] = src
                destination[subject][relation] = dst

    f = example.frame
    add(f.primary_subject, f.primary_source, f.primary_destination, f.primary_relations)
    if f.secondary_present:
        add(f.secondary_subject, f.secondary_source, f.secondary_destination, f.secondary_relations)

    obligation_active = int(f.return_obligation)
    obligation = (
        (f.primary_subject, f.primary_destination, f.primary_source)
        if obligation_active else (NONE_SLOT, NONE_SLOT, NONE_SLOT)
    )
    return masks, source, destination, obligation_active, obligation


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="google/bert_uncased_L-2_H-128_A-2")
    p.add_argument("--train-samples", type=int, default=512)
    p.add_argument("--eval-samples", type=int, default=96)
    p.add_argument("--epochs", type=int, default=14)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--backbone-lr", type=float, default=5e-5)
    p.add_argument("--head-lr", type=float, default=5e-4)
    p.add_argument("--semantic-dim", type=int, default=32)
    p.add_argument("--seed", type=int, default=43)
    args = p.parse_args()

    import torch
    import torch.nn as nn
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    train = generate_delta_examples(args.train_samples, split="train", seed=23)
    evaluation = generate_delta_examples(args.eval_samples, split="eval", seed=24)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    backbone = AutoModel.from_pretrained(args.model)
    hidden = int(backbone.config.hidden_size)
    d = args.semantic_dim

    class Model(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = backbone
            self.entity_projection = nn.Linear(hidden, d, bias=False)
            self.global_projection = nn.Linear(hidden, d, bias=False)
            self.mask_head = nn.Linear(d, SUBSET_COUNT)
            self.relation_embedding = nn.Parameter(torch.empty(RELATION_COUNT, d))
            nn.init.normal_(self.relation_embedding, std=d ** -0.5)
            self.source_query = nn.Linear(d, d, bias=False)
            self.destination_query = nn.Linear(d, d, bias=False)
            self.source_none = nn.Linear(d, 1)
            self.destination_none = nn.Linear(d, 1)
            self.obligation_active = nn.Linear(hidden, 1)
            self.obligation_queries = nn.Linear(hidden, 3 * d)
            self.obligation_none = nn.Linear(hidden, 3)

        def forward(self, input_ids, attention_mask, positions, present, token_type_ids=None):
            kw = {"input_ids": input_ids, "attention_mask": attention_mask}
            if token_type_ids is not None:
                kw["token_type_ids"] = token_type_ids
            states = self.backbone(**kw).last_hidden_state
            pooled = states[:, 0]
            b = states.shape[0]
            ep = positions.clamp_min(0)
            entity_states = states[torch.arange(b).unsqueeze(1), ep]
            entity = self.entity_projection(entity_states)
            global_state = self.global_projection(pooled)[:, None, :]
            subject_state = torch.tanh(entity + global_state)
            mask_logits = self.mask_head(subject_state)
            mask_logits = mask_logits.masked_fill(~present[:, :, None], -1e9)
            # Absent slots are deterministically NONE; keep class 0 available.
            mask_logits[:, :, 0] = torch.where(present, mask_logits[:, :, 0], torch.zeros_like(mask_logits[:, :, 0]))

            cells = torch.tanh(subject_state[:, :, None, :] + self.relation_embedding[None, None, :, :])
            keys = entity
            src_q = self.source_query(cells)
            dst_q = self.destination_query(cells)
            src = torch.einsum("bsrd,btd->bsrt", src_q, keys) / (d ** 0.5)
            dst = torch.einsum("bsrd,btd->bsrt", dst_q, keys) / (d ** 0.5)
            src = src.masked_fill(~present[:, None, None, :], -1e9)
            dst = dst.masked_fill(~present[:, None, None, :], -1e9)
            src = torch.cat((src, self.source_none(cells)), dim=-1)
            dst = torch.cat((dst, self.destination_none(cells)), dim=-1)

            oa = self.obligation_active(pooled).squeeze(-1)
            oq = self.obligation_queries(pooled).view(b, 3, d)
            op = torch.einsum("brd,bsd->brs", oq, keys) / (d ** 0.5)
            op = op.masked_fill(~present[:, None, :], -1e9)
            op = torch.cat((op, self.obligation_none(pooled).unsqueeze(-1)), dim=-1)
            return mask_logits, src, dst, oa, op

    model = Model()
    total = sum(x.numel() for x in model.parameters())
    backbone_n = sum(x.numel() for x in model.backbone.parameters())
    head_n = total - backbone_n
    head_params = [x for name, x in model.named_parameters() if not name.startswith("backbone.")]
    opt = torch.optim.AdamW([
        {"params": model.backbone.parameters(), "lr": args.backbone_lr},
        {"params": head_params, "lr": args.head_lr},
    ], weight_decay=0.01)
    ce = nn.CrossEntropyLoss()
    bce_ob = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(3.0))
    rng = random.Random(args.seed)

    def encode(group):
        texts = [x.text for x in group]
        enc = tokenizer(texts, padding=True, truncation=True, max_length=96,
                        return_tensors="pt", return_offsets_mapping=True)
        offsets = enc.pop("offset_mapping")
        positions = torch.full((len(group), MAX_SLOTS), -1, dtype=torch.long)
        present = torch.zeros((len(group), MAX_SLOTS), dtype=torch.bool)
        for row, text in enumerate(texts):
            for slot, (cs, ce_) in marker_spans(text).items():
                for ti, (s, e) in enumerate(offsets[row].tolist()):
                    if s < ce_ and e > cs:
                        positions[row, slot] = ti
                        present[row, slot] = True
                        break
        ts = [targets(x) for x in group]
        return (enc, positions, present,
                torch.tensor([x[0] for x in ts], dtype=torch.long),
                torch.tensor([x[1] for x in ts], dtype=torch.long),
                torch.tensor([x[2] for x in ts], dtype=torch.long),
                torch.tensor([x[3] for x in ts], dtype=torch.float32),
                torch.tensor([x[4] for x in ts], dtype=torch.long))

    history = []
    model.train()
    for epoch in range(args.epochs):
        tot = seen = 0
        for group in batches(train, args.batch_size, rng):
            enc, pos, present, masks, src, dst, oa, optr = encode(group)
            opt.zero_grad(set_to_none=True)
            ml, sl, dl, oal, opl = model(enc["input_ids"], enc["attention_mask"], pos, present, enc.get("token_type_ids"))
            loss = ce(ml[present], masks[present])
            active = torch.zeros_like(src, dtype=torch.bool)
            for r in range(RELATION_COUNT):
                active[:, :, r] = ((masks >> r) & 1).bool()
            if bool(active.any()):
                loss = loss + ce(sl[active], src[active]) + ce(dl[active], dst[active])
            loss = loss + bce_ob(oal, oa)
            om = oa > .5
            if bool(om.any()):
                for role in range(3):
                    loss = loss + ce(opl[om, role], optr[om, role])
            loss.backward(); opt.step()
            tot += float(loss.detach()) * len(group); seen += len(group)
        avg = tot / seen; history.append(avg); print(f"epoch={epoch+1} average_loss={avg:.6f}")

    exact = mask_correct = mask_total = ptr_correct = ptr_total = 0
    fam = defaultdict(lambda: {"exact": 0, "total": 0})
    mistakes = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(evaluation), args.batch_size):
            group = list(evaluation[start:start+args.batch_size])
            enc, pos, present, masks, src, dst, oa, optr = encode(group)
            ml, sl, dl, oal, opl = model(enc["input_ids"], enc["attention_mask"], pos, present, enc.get("token_type_ids"))
            pm = ml.argmax(-1); ps = sl.argmax(-1); pd = dl.argmax(-1)
            poa = (oal.sigmoid() >= .5).long(); pop = opl.argmax(-1)
            for row, ex in enumerate(group):
                # Absent slots are deterministically mask=0.
                pm[row, ~present[row]] = 0
                mask_correct += int((pm[row] == masks[row]).sum()); mask_total += MAX_SLOTS
                for s in range(MAX_SLOTS):
                    for r in range(RELATION_COUNT):
                        if (int(masks[row,s]) >> r) & 1:
                            ptr_correct += int(ps[row,s,r] == src[row,s,r])
                            ptr_correct += int(pd[row,s,r] == dst[row,s,r]); ptr_total += 2
                # Canonicalize inactive pointers.
                cps = ps[row].clone(); cpd = pd[row].clone()
                for s in range(MAX_SLOTS):
                    for r in range(RELATION_COUNT):
                        if not ((int(pm[row,s]) >> r) & 1):
                            cps[s,r] = NONE_SLOT; cpd[s,r] = NONE_SLOT
                cop = pop[row].clone()
                if int(poa[row]) == 0: cop[:] = NONE_SLOT
                ok = (torch.equal(pm[row], masks[row]) and torch.equal(cps, src[row]) and
                      torch.equal(cpd, dst[row]) and int(poa[row]) == int(oa[row]) and
                      torch.equal(cop, optr[row]))
                exact += int(ok); fam[ex.family]["exact"] += int(ok); fam[ex.family]["total"] += 1
                if not ok and len(mistakes) < 24:
                    mistakes.append({"text": ex.text, "family": ex.family,
                        "gold_masks": masks[row].tolist(), "predicted_masks": pm[row].tolist(),
                        "gold_obligation": int(oa[row]), "predicted_obligation": int(poa[row]),
                        "slots": list(ex.slots)})

    report = {"model": args.model, "mode": "per_entity_relation_subset_grid",
              "total_parameters": total, "backbone_parameters": backbone_n, "head_parameters": head_n,
              "train_samples": len(train), "eval_samples": len(evaluation), "epochs": args.epochs,
              "relation_subset_accuracy": mask_correct / mask_total,
              "active_pointer_accuracy": ptr_correct / max(ptr_total,1),
              "exact_frame": exact, "exact_frame_accuracy": exact / len(evaluation),
              "family_exact": dict(fam), "loss_history": history, "mistakes": mistakes,
              "contract": {"event_classes": False, "primary_secondary_order": False,
                           "relation_subsets_per_entity": True, "free_form_generation": False}}
    Path("compiler-relation-subset-results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("model","mode","total_parameters","head_parameters",
        "relation_subset_accuracy","active_pointer_accuracy","exact_frame","exact_frame_accuracy",
        "family_exact","loss_history")}, indent=2))

if __name__ == "__main__":
    main()

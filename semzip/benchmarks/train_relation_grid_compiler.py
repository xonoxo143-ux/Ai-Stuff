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


def grid_targets(example: DeltaExample):
    # [subject slot][relation] -> active/source/destination. No event-class or
    # primary/secondary ordering survives into this representation.
    active = [[0] * RELATION_COUNT for _ in range(MAX_SLOTS)]
    source = [[NONE_SLOT] * RELATION_COUNT for _ in range(MAX_SLOTS)]
    destination = [[NONE_SLOT] * RELATION_COUNT for _ in range(MAX_SLOTS)]

    def add_delta(subject: int, src: int, dst: int, bits):
        if subject == NONE_SLOT:
            return
        for relation, enabled in enumerate(bits):
            if not enabled:
                continue
            if active[subject][relation]:
                raise ValueError("one event cannot contain two changes for the same subject/relation cell")
            active[subject][relation] = 1
            source[subject][relation] = src
            destination[subject][relation] = dst

    f = example.frame
    add_delta(f.primary_subject, f.primary_source, f.primary_destination, f.primary_relations)
    if f.secondary_present:
        add_delta(f.secondary_subject, f.secondary_source, f.secondary_destination, f.secondary_relations)

    # Return obligation stays a separate effect family for now; it is not a current-world
    # owner/possessor/location relation.
    obligation_active = int(f.return_obligation)
    if obligation_active:
        obligation = (f.primary_subject, f.primary_destination, f.primary_source)
    else:
        obligation = (NONE_SLOT, NONE_SLOT, NONE_SLOT)

    return active, source, destination, obligation_active, obligation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google/bert_uncased_L-2_H-128_A-2")
    parser.add_argument("--train-samples", type=int, default=512)
    parser.add_argument("--eval-samples", type=int, default=96)
    parser.add_argument("--epochs", type=int, default=14)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--backbone-lr", type=float, default=5e-5)
    parser.add_argument("--head-lr", type=float, default=5e-4)
    parser.add_argument("--semantic-dim", type=int, default=32)
    parser.add_argument("--seed", type=int, default=41)
    args = parser.parse_args()

    import torch
    import torch.nn as nn
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))

    train = generate_delta_examples(args.train_samples, split="train", seed=23)
    evaluation = generate_delta_examples(args.eval_samples, split="eval", seed=24)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("relation-grid compiler requires tokenizer offsets")
    backbone = AutoModel.from_pretrained(args.model)
    hidden = int(backbone.config.hidden_size)
    d = args.semantic_dim

    class RelationGridCompiler(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = backbone
            self.entity_key = nn.Linear(hidden, d, bias=False)
            self.entity_subject = nn.Linear(hidden, d, bias=False)
            self.global_projection = nn.Linear(hidden, d, bias=False)
            self.relation_embedding = nn.Parameter(torch.empty(RELATION_COUNT, d))
            nn.init.normal_(self.relation_embedding, std=d ** -0.5)

            self.active_head = nn.Linear(d, 1)
            self.source_query = nn.Linear(d, d, bias=False)
            self.destination_query = nn.Linear(d, d, bias=False)
            self.source_none = nn.Linear(d, 1)
            self.destination_none = nn.Linear(d, 1)

            self.obligation_active = nn.Linear(hidden, 1)
            self.obligation_queries = nn.Linear(hidden, 3 * d)
            self.obligation_none = nn.Linear(hidden, 3)

        def _pointer_logits(self, query, keys, present, none_logits):
            # query [..., d], keys [B, slots, d]
            scores = torch.einsum("bsrd,btd->bsrt", query, keys) / (d ** 0.5)
            scores = scores.masked_fill(~present[:, None, None, :], -1e9)
            return torch.cat((scores, none_logits.unsqueeze(-1)), dim=-1)

        def forward(self, input_ids, attention_mask, entity_positions, entity_present, token_type_ids=None):
            kwargs = {"input_ids": input_ids, "attention_mask": attention_mask}
            if token_type_ids is not None:
                kwargs["token_type_ids"] = token_type_ids
            states = self.backbone(**kwargs).last_hidden_state
            pooled = states[:, 0]
            batch = states.shape[0]
            safe_positions = entity_positions.clamp_min(0)
            entity_states = states[torch.arange(batch).unsqueeze(1), safe_positions]

            keys = self.entity_key(entity_states)
            subject = self.entity_subject(entity_states)[:, :, None, :]
            global_state = self.global_projection(pooled)[:, None, None, :]
            relation = self.relation_embedding[None, None, :, :]
            cells = torch.tanh(subject + global_state + relation)  # [B, slots, relations, d]

            active_logits = self.active_head(cells).squeeze(-1)
            source_q = self.source_query(cells)
            destination_q = self.destination_query(cells)
            source_logits = self._pointer_logits(source_q, keys, entity_present, self.source_none(cells).squeeze(-1))
            destination_logits = self._pointer_logits(
                destination_q, keys, entity_present, self.destination_none(cells).squeeze(-1)
            )

            obligation_active = self.obligation_active(pooled).squeeze(-1)
            obligation_q = self.obligation_queries(pooled).view(batch, 3, d)
            obligation_scores = torch.einsum("brd,bsd->brs", obligation_q, keys) / (d ** 0.5)
            obligation_scores = obligation_scores.masked_fill(~entity_present[:, None, :], -1e9)
            obligation_logits = torch.cat(
                (obligation_scores, self.obligation_none(pooled).unsqueeze(-1)), dim=-1
            )
            return active_logits, source_logits, destination_logits, obligation_active, obligation_logits

    model = RelationGridCompiler()
    total_parameters = sum(p.numel() for p in model.parameters())
    backbone_parameters = sum(p.numel() for p in model.backbone.parameters())
    head_parameters = total_parameters - backbone_parameters

    head_params = [p for name, p in model.named_parameters() if not name.startswith("backbone.")]
    optimizer = torch.optim.AdamW(
        [
            {"params": model.backbone.parameters(), "lr": args.backbone_lr},
            {"params": head_params, "lr": args.head_lr},
        ], weight_decay=0.01,
    )
    active_loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(4.0))
    obligation_active_loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(3.0))
    pointer_loss_fn = nn.CrossEntropyLoss()
    rng = random.Random(args.seed)

    def encode(group: list[DeltaExample]):
        texts = [x.text for x in group]
        encoded = tokenizer(
            texts, padding=True, truncation=True, max_length=96,
            return_tensors="pt", return_offsets_mapping=True,
        )
        offsets = encoded.pop("offset_mapping")
        positions = torch.full((len(group), MAX_SLOTS), -1, dtype=torch.long)
        present = torch.zeros((len(group), MAX_SLOTS), dtype=torch.bool)
        for row, text in enumerate(texts):
            for slot, (char_start, char_end) in marker_spans(text).items():
                for token_index, (start, end) in enumerate(offsets[row].tolist()):
                    if start < char_end and end > char_start:
                        positions[row, slot] = token_index
                        present[row, slot] = True
                        break
                if not present[row, slot]:
                    raise RuntimeError(f"could not map E{slot} in {text!r}")

        targets = [grid_targets(x) for x in group]
        active = torch.tensor([t[0] for t in targets], dtype=torch.float32)
        source = torch.tensor([t[1] for t in targets], dtype=torch.long)
        destination = torch.tensor([t[2] for t in targets], dtype=torch.long)
        obligation_active = torch.tensor([t[3] for t in targets], dtype=torch.float32)
        obligation = torch.tensor([t[4] for t in targets], dtype=torch.long)
        return encoded, positions, present, active, source, destination, obligation_active, obligation

    loss_history = []
    model.train()
    for epoch in range(args.epochs):
        total_loss = 0.0
        seen = 0
        for group in batches(train, args.batch_size, rng):
            encoded, positions, present, active, source, destination, obligation_active, obligation = encode(group)
            optimizer.zero_grad(set_to_none=True)
            outputs = model(
                encoded["input_ids"], encoded["attention_mask"], positions, present,
                encoded.get("token_type_ids"),
            )
            active_logits, source_logits, destination_logits, obligation_active_logits, obligation_logits = outputs
            loss = active_loss_fn(active_logits, active)
            active_mask = active > 0.5
            if bool(active_mask.any()):
                loss = loss + pointer_loss_fn(source_logits[active_mask], source[active_mask])
                loss = loss + pointer_loss_fn(destination_logits[active_mask], destination[active_mask])
            loss = loss + obligation_active_loss_fn(obligation_active_logits, obligation_active)
            obligation_mask = obligation_active > 0.5
            if bool(obligation_mask.any()):
                for role in range(3):
                    loss = loss + pointer_loss_fn(
                        obligation_logits[obligation_mask, role, :],
                        obligation[obligation_mask, role],
                    )
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(group)
            seen += len(group)
        average = total_loss / max(seen, 1)
        loss_history.append(average)
        print(f"epoch={epoch + 1} average_loss={average:.6f}")

    model.eval()
    exact = 0
    cell_active_correct = cell_active_total = 0
    active_pointer_correct = active_pointer_total = 0
    family_exact = defaultdict(lambda: {"exact": 0, "total": 0})
    mistakes = []

    with torch.no_grad():
        for start in range(0, len(evaluation), args.batch_size):
            group = list(evaluation[start:start + args.batch_size])
            encoded, positions, present, active, source, destination, obligation_active, obligation = encode(group)
            outputs = model(
                encoded["input_ids"], encoded["attention_mask"], positions, present,
                encoded.get("token_type_ids"),
            )
            active_logits, source_logits, destination_logits, obligation_active_logits, obligation_logits = outputs
            pred_active = (active_logits.sigmoid() >= 0.5).to(torch.long)
            pred_source = source_logits.argmax(dim=-1)
            pred_destination = destination_logits.argmax(dim=-1)
            pred_obligation_active = (obligation_active_logits.sigmoid() >= 0.5).to(torch.long)
            pred_obligation = obligation_logits.argmax(dim=-1)
            gold_active = active.to(torch.long)
            gold_obligation_active = obligation_active.to(torch.long)

            for row, example in enumerate(group):
                pa = pred_active[row]
                ga = gold_active[row]
                cell_active_correct += int((pa == ga).sum())
                cell_active_total += pa.numel()

                # Canonical resolved form: inactive cells carry no pointers.
                ps = pred_source[row].clone()
                pd = pred_destination[row].clone()
                ps[pa == 0] = NONE_SLOT
                pd[pa == 0] = NONE_SLOT
                gs = source[row]
                gd = destination[row]

                gold_active_cells = ga == 1
                active_pointer_correct += int((ps[gold_active_cells] == gs[gold_active_cells]).sum())
                active_pointer_correct += int((pd[gold_active_cells] == gd[gold_active_cells]).sum())
                active_pointer_total += int(gold_active_cells.sum()) * 2

                poa = int(pred_obligation_active[row])
                goa = int(gold_obligation_active[row])
                po = pred_obligation[row].clone()
                if poa == 0:
                    po[:] = NONE_SLOT

                is_exact = (
                    torch.equal(pa, ga)
                    and torch.equal(ps, gs)
                    and torch.equal(pd, gd)
                    and poa == goa
                    and torch.equal(po, obligation[row])
                )
                exact += int(is_exact)
                family_exact[example.family]["exact"] += int(is_exact)
                family_exact[example.family]["total"] += 1
                if not is_exact and len(mistakes) < 24:
                    mistakes.append({
                        "text": example.text,
                        "family": example.family,
                        "gold_active": ga.tolist(),
                        "predicted_active": pa.tolist(),
                        "gold_source": gs.tolist(),
                        "predicted_source": ps.tolist(),
                        "gold_destination": gd.tolist(),
                        "predicted_destination": pd.tolist(),
                        "gold_obligation_active": goa,
                        "predicted_obligation_active": poa,
                        "gold_obligation": obligation[row].tolist(),
                        "predicted_obligation": po.tolist(),
                        "slots": list(example.slots),
                    })

    report = {
        "model": args.model,
        "mode": "relation_change_grid",
        "relations": list(RELATIONS),
        "semantic_dim": d,
        "train_samples": len(train), "eval_samples": len(evaluation),
        "epochs": args.epochs,
        "total_parameters": total_parameters,
        "backbone_parameters": backbone_parameters,
        "head_parameters": head_parameters,
        "trainable_parameters": total_parameters,
        "cell_active_accuracy": cell_active_correct / cell_active_total,
        "active_pointer_accuracy": active_pointer_correct / max(active_pointer_total, 1),
        "exact_frame": exact,
        "exact_frame_accuracy": exact / len(evaluation),
        "family_exact": dict(family_exact),
        "loss_history": loss_history,
        "mistakes": mistakes,
        "contract": {
            "primary_secondary_order": False,
            "lexical_action_classes": False,
            "free_form_generation": False,
            "world_relation_cells": True,
            "bidirectional_encoder": True,
        },
    }
    Path("compiler-relation-grid-results.json").write_text(json.dumps(report, indent=2))
    output = Path("semvm-relation-grid-compiler")
    output.mkdir(exist_ok=True)
    model.backbone.save_pretrained(output)
    tokenizer.save_pretrained(output)
    torch.save({
        "entity_key": model.entity_key.state_dict(),
        "entity_subject": model.entity_subject.state_dict(),
        "global_projection": model.global_projection.state_dict(),
        "relation_embedding": model.relation_embedding.detach().cpu(),
        "active_head": model.active_head.state_dict(),
        "source_query": model.source_query.state_dict(),
        "destination_query": model.destination_query.state_dict(),
        "source_none": model.source_none.state_dict(),
        "destination_none": model.destination_none.state_dict(),
        "obligation_active": model.obligation_active.state_dict(),
        "obligation_queries": model.obligation_queries.state_dict(),
        "obligation_none": model.obligation_none.state_dict(),
        "hidden_size": hidden, "semantic_dim": d,
    }, output / "semantic_grid_heads.pt")

    print(json.dumps({k: report[k] for k in (
        "model", "mode", "semantic_dim", "total_parameters", "head_parameters",
        "train_samples", "eval_samples", "epochs", "cell_active_accuracy",
        "active_pointer_accuracy", "exact_frame", "exact_frame_accuracy",
        "family_exact", "loss_history"
    )}, indent=2))


if __name__ == "__main__":
    main()

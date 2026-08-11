from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
import random
import re
from pathlib import Path

from compiler_delta_corpus import MAX_SLOTS, NONE_SLOT, RELATIONS, DeltaExample, generate_delta_examples


QUERY_TOKENS = {
    "owner": "[REL0]",
    "possessor": "[REL1]",
    "location": "[REL2]",
    "return": "[EFF0]",
}
TARGET_TOKEN = "[TARGET]"


@dataclass(frozen=True, slots=True)
class Probe:
    query_kind: str
    subject: int
    active: int
    source: int
    destination: int


def marker_spans(text: str):
    out = {}
    for slot in range(MAX_SLOTS):
        m = re.search(rf"(?<![A-Za-z0-9_])E{slot}(?![A-Za-z0-9_])", text)
        if m:
            out[slot] = m.span()
    return out


def frame_grid(example: DeltaExample):
    source = [[NONE_SLOT] * len(RELATIONS) for _ in range(MAX_SLOTS)]
    destination = [[NONE_SLOT] * len(RELATIONS) for _ in range(MAX_SLOTS)]

    def add(subject, src, dst, bits):
        if subject == NONE_SLOT:
            return
        for relation, enabled in enumerate(bits):
            if enabled:
                if source[subject][relation] != NONE_SLOT:
                    raise ValueError("duplicate subject/relation transition")
                source[subject][relation] = src
                destination[subject][relation] = dst

    f = example.frame
    add(f.primary_subject, f.primary_source, f.primary_destination, f.primary_relations)
    if f.secondary_present:
        add(f.secondary_subject, f.secondary_source, f.secondary_destination, f.secondary_relations)

    if f.return_obligation:
        obligation = (f.primary_subject, f.primary_destination, f.primary_source)
    else:
        obligation = None
    return source, destination, obligation


def probes_for(example: DeltaExample):
    source, destination, obligation = frame_grid(example)
    present_slots = tuple(int(slot[0][1:]) for slot in example.slots)
    probes = []
    for subject in present_slots:
        for r, relation in enumerate(RELATIONS):
            src = source[subject][r]
            dst = destination[subject][r]
            active = int(src != NONE_SLOT or dst != NONE_SLOT)
            probes.append(Probe(relation, subject, active, src, dst))
        if obligation is not None and obligation[0] == subject:
            probes.append(Probe("return", subject, 1, obligation[1], obligation[2]))
        else:
            probes.append(Probe("return", subject, 0, NONE_SLOT, NONE_SLOT))
    return tuple(probes)


def query_text(example: DeltaExample, probe: Probe) -> str:
    # The query is anonymous. The target entity is marked in-place so the same
    # architecture works for any E-slot without learning separate SUB0/SUB1 heads.
    marker = f"E{probe.subject}"
    marked = re.sub(
        rf"(?<![A-Za-z0-9_]){re.escape(marker)}(?![A-Za-z0-9_])",
        f"{TARGET_TOKEN} {marker}",
        example.text,
        count=1,
    )
    if marked == example.text:
        raise ValueError(f"target marker {marker} not found in {example.text!r}")
    return f"{QUERY_TOKENS[probe.query_kind]} {marked}"


def batches(items, size, rng):
    indices = list(range(len(items)))
    rng.shuffle(indices)
    for start in range(0, len(indices), size):
        yield [items[i] for i in indices[start:start + size]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="google/bert_uncased_L-2_H-128_A-2")
    ap.add_argument("--train-samples", type=int, default=512)
    ap.add_argument("--eval-samples", type=int, default=96)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--backbone-lr", type=float, default=5e-5)
    ap.add_argument("--head-lr", type=float, default=5e-4)
    ap.add_argument("--semantic-dim", type=int, default=32)
    ap.add_argument("--seed", type=int, default=53)
    args = ap.parse_args()

    import torch
    import torch.nn as nn
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))

    train_examples = generate_delta_examples(args.train_samples, split="train", seed=23)
    eval_examples = generate_delta_examples(args.eval_samples, split="eval", seed=24)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    tokenizer.add_special_tokens({
        "additional_special_tokens": list(QUERY_TOKENS.values()) + [TARGET_TOKEN]
    })
    backbone = AutoModel.from_pretrained(args.model)
    backbone.resize_token_embeddings(len(tokenizer))
    hidden = int(backbone.config.hidden_size)
    d = args.semantic_dim

    class ProbeModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = backbone
            self.entity_key = nn.Linear(hidden, d, bias=False)
            self.source_query = nn.Linear(hidden, d, bias=False)
            self.destination_query = nn.Linear(hidden, d, bias=False)
            self.active_head = nn.Linear(hidden, 1)

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
            src_q = self.source_query(pooled)
            dst_q = self.destination_query(pooled)
            src_logits = torch.einsum("bd,bsd->bs", src_q, keys) / (d ** 0.5)
            dst_logits = torch.einsum("bd,bsd->bs", dst_q, keys) / (d ** 0.5)
            src_logits = src_logits.masked_fill(~entity_present, -1e9)
            dst_logits = dst_logits.masked_fill(~entity_present, -1e9)
            return self.active_head(pooled).squeeze(-1), src_logits, dst_logits

    model = ProbeModel()
    total_parameters = sum(p.numel() for p in model.parameters())
    backbone_parameters = sum(p.numel() for p in model.backbone.parameters())
    head_parameters = total_parameters - backbone_parameters
    head_params = [p for name, p in model.named_parameters() if not name.startswith("backbone.")]
    optimizer = torch.optim.AdamW([
        {"params": model.backbone.parameters(), "lr": args.backbone_lr},
        {"params": head_params, "lr": args.head_lr},
    ], weight_decay=0.01)
    active_loss = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(3.0))
    pointer_loss = nn.CrossEntropyLoss()
    rng = random.Random(args.seed)

    train_rows = tuple((example, probe) for example in train_examples for probe in probes_for(example))

    def encode(rows):
        texts = [query_text(example, probe) for example, probe in rows]
        encoded = tokenizer(
            texts, padding=True, truncation=True, max_length=112,
            return_tensors="pt", return_offsets_mapping=True,
        )
        offsets = encoded.pop("offset_mapping")
        positions = torch.full((len(rows), MAX_SLOTS), -1, dtype=torch.long)
        present = torch.zeros((len(rows), MAX_SLOTS), dtype=torch.bool)
        for row, text in enumerate(texts):
            for slot, (char_start, char_end) in marker_spans(text).items():
                for token_index, (start, end) in enumerate(offsets[row].tolist()):
                    if start < char_end and end > char_start:
                        positions[row, slot] = token_index
                        present[row, slot] = True
                        break
                if not present[row, slot]:
                    raise RuntimeError(f"could not map E{slot} in {text!r}")
        active = torch.tensor([probe.active for _, probe in rows], dtype=torch.float32)
        source = torch.tensor([probe.source if probe.active else 0 for _, probe in rows], dtype=torch.long)
        destination = torch.tensor([probe.destination if probe.active else 0 for _, probe in rows], dtype=torch.long)
        return encoded, positions, present, active, source, destination

    loss_history = []
    model.train()
    for epoch in range(args.epochs):
        total_loss = 0.0
        seen = 0
        for group in batches(train_rows, args.batch_size, rng):
            encoded, positions, present, active, source, destination = encode(group)
            optimizer.zero_grad(set_to_none=True)
            active_logits, source_logits, destination_logits = model(
                encoded["input_ids"], encoded["attention_mask"], positions, present,
                encoded.get("token_type_ids"),
            )
            loss = active_loss(active_logits, active)
            positive = active > 0.5
            if bool(positive.any()):
                loss = loss + pointer_loss(source_logits[positive], source[positive])
                loss = loss + pointer_loss(destination_logits[positive], destination[positive])
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(group)
            seen += len(group)
        avg = total_loss / seen
        loss_history.append(avg)
        print(f"epoch={epoch+1} average_loss={avg:.6f}")

    exact = 0
    probe_active_correct = probe_active_total = 0
    positive_pointer_correct = positive_pointer_total = 0
    family_exact = defaultdict(lambda: {"exact": 0, "total": 0})
    mistakes = []
    model.eval()

    with torch.no_grad():
        for example in eval_examples:
            probes = probes_for(example)
            rows = [(example, probe) for probe in probes]
            encoded, positions, present, active, source, destination = encode(rows)
            active_logits, source_logits, destination_logits = model(
                encoded["input_ids"], encoded["attention_mask"], positions, present,
                encoded.get("token_type_ids"),
            )
            predicted_active = (active_logits.sigmoid() >= 0.5).to(torch.long)
            predicted_source = source_logits.argmax(dim=-1)
            predicted_destination = destination_logits.argmax(dim=-1)

            prediction_rows = []
            example_ok = True
            for i, probe in enumerate(probes):
                gold_active = probe.active
                pred_active = int(predicted_active[i])
                probe_active_correct += int(gold_active == pred_active)
                probe_active_total += 1
                if gold_active:
                    positive_pointer_correct += int(int(predicted_source[i]) == probe.source)
                    positive_pointer_correct += int(int(predicted_destination[i]) == probe.destination)
                    positive_pointer_total += 2
                if pred_active != gold_active:
                    example_ok = False
                elif gold_active and (
                    int(predicted_source[i]) != probe.source
                    or int(predicted_destination[i]) != probe.destination
                ):
                    example_ok = False
                if pred_active:
                    prediction_rows.append({
                        "query": probe.query_kind,
                        "subject": probe.subject,
                        "source": int(predicted_source[i]),
                        "destination": int(predicted_destination[i]),
                    })

            exact += int(example_ok)
            family_exact[example.family]["exact"] += int(example_ok)
            family_exact[example.family]["total"] += 1
            if not example_ok and len(mistakes) < 24:
                mistakes.append({
                    "text": example.text,
                    "family": example.family,
                    "gold": [probe.__dict__ if hasattr(probe, "__dict__") else {
                        "query_kind": probe.query_kind,
                        "subject": probe.subject,
                        "active": probe.active,
                        "source": probe.source,
                        "destination": probe.destination,
                    } for probe in probes if probe.active],
                    "predicted": prediction_rows,
                    "slots": list(example.slots),
                })

    report = {
        "model": args.model,
        "mode": "query_conditioned_semantic_probes",
        "query_types": list(QUERY_TOKENS),
        "total_parameters": total_parameters,
        "backbone_parameters": backbone_parameters,
        "head_parameters": head_parameters,
        "train_examples": len(train_examples),
        "train_probes": len(train_rows),
        "eval_examples": len(eval_examples),
        "epochs": args.epochs,
        "probe_active_accuracy": probe_active_correct / probe_active_total,
        "positive_pointer_accuracy": positive_pointer_correct / max(positive_pointer_total, 1),
        "exact_patch": exact,
        "exact_patch_accuracy": exact / len(eval_examples),
        "family_exact": dict(family_exact),
        "loss_history": loss_history,
        "mistakes": mistakes,
        "contract": {
            "relation_conditioned_encoder": True,
            "subject_conditioned_by_target_marker": True,
            "arbitrary_patch_size": True,
            "relation_combinations_are_unions_of_independent_probes": True,
            "free_form_generation": False,
            "lexical_event_classes": False,
        },
    }
    Path("compiler-semantic-probe-results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in (
        "model", "mode", "total_parameters", "head_parameters", "train_examples",
        "train_probes", "eval_examples", "epochs", "probe_active_accuracy",
        "positive_pointer_accuracy", "exact_patch", "exact_patch_accuracy",
        "family_exact", "loss_history"
    )}, indent=2))


if __name__ == "__main__":
    main()

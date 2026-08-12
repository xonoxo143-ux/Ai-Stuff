from __future__ import annotations

import argparse
from collections import defaultdict
import json
import random
import re
from pathlib import Path

from compiler_raw_semantic_corpus import RawSemanticExample, generate_raw_semantic_examples
from train_semantic_probe_compiler import QUERY_TOKENS, TARGET_TOKEN, probes_for, query_text
from semzip.vm_delta import RelationDelta
from semzip.vm_mentions import slotize_mentions
from semzip.vm_patch import ReturnObligation, SemanticPatch


LABEL_O = 0
LABEL_B = 1
LABEL_I = 2
MAX_SLOTS = 4
RELATIONS = ("owner", "possessor", "location")


def batches(items, size, rng):
    indices = list(range(len(items)))
    rng.shuffle(indices)
    for start in range(0, len(indices), size):
        yield [items[i] for i in indices[start:start + size]]


def marker_spans(text: str):
    result = {}
    for slot in range(MAX_SLOTS):
        match = re.search(rf"(?<![A-Za-z0-9_])E{slot}(?![A-Za-z0-9_])", text)
        if match:
            result[slot] = match.span()
    return result


def gold_patch(example: RawSemanticExample) -> SemanticPatch:
    frame = example.slotted.frame
    entities = example.mentions
    deltas = []

    def add(subject, source, destination, bits):
        relations = tuple(name for name, enabled in zip(RELATIONS, bits) if enabled)
        if relations:
            deltas.append(
                RelationDelta.build(
                    entities[subject], entities[source], entities[destination], relations
                )
            )

    add(
        frame.primary_subject,
        frame.primary_source,
        frame.primary_destination,
        frame.primary_relations,
    )
    if frame.secondary_present:
        add(
            frame.secondary_subject,
            frame.secondary_source,
            frame.secondary_destination,
            frame.secondary_relations,
        )
    obligations = ()
    if frame.return_obligation:
        obligations = (
            ReturnObligation.build(
                entities[frame.primary_subject],
                entities[frame.primary_destination],
                entities[frame.primary_source],
            ),
        )
    return SemanticPatch.build(tuple(deltas), return_obligations=obligations)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="google/bert_uncased_L-2_H-128_A-2")
    ap.add_argument("--train-samples", type=int, default=2048)
    ap.add_argument("--eval-samples", type=int, default=256)
    ap.add_argument("--mention-epochs", type=int, default=8)
    ap.add_argument("--semantic-epochs", type=int, default=8)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--semantic-batch-size", type=int, default=64)
    ap.add_argument("--backbone-lr", type=float, default=5e-5)
    ap.add_argument("--head-lr", type=float, default=5e-4)
    ap.add_argument("--semantic-dim", type=int, default=32)
    ap.add_argument("--seed", type=int, default=79)
    args = ap.parse_args()

    import torch
    import torch.nn as nn
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))

    train = generate_raw_semantic_examples(args.train_samples, split="train", seed=31)
    evaluation = generate_raw_semantic_examples(args.eval_samples, split="eval", seed=32)

    # ------------------------------------------------------------------
    # Stage 1: raw text -> mention spans. Same tiny architecture family,
    # but kept as a separate backbone in this diagnostic so error attribution
    # is clean. A later experiment can share the encoder.
    # ------------------------------------------------------------------
    mention_tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    mention_backbone = AutoModel.from_pretrained(args.model)
    hidden = int(mention_backbone.config.hidden_size)

    class MentionDetector(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = mention_backbone
            self.head = nn.Linear(hidden, 3)

        def forward(self, input_ids, attention_mask, token_type_ids=None):
            kwargs = {"input_ids": input_ids, "attention_mask": attention_mask}
            if token_type_ids is not None:
                kwargs["token_type_ids"] = token_type_ids
            return self.head(self.backbone(**kwargs).last_hidden_state)

    mention_model = MentionDetector()
    mention_optimizer = torch.optim.AdamW(
        [
            {"params": mention_model.backbone.parameters(), "lr": args.backbone_lr},
            {"params": mention_model.head.parameters(), "lr": args.head_lr},
        ],
        weight_decay=0.01,
    )
    mention_loss = nn.CrossEntropyLoss(
        weight=torch.tensor([0.25, 1.0, 1.0]), ignore_index=-100
    )

    def encode_mentions(group):
        texts = [x.raw_text for x in group]
        encoded = mention_tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
            return_offsets_mapping=True,
        )
        offsets = encoded.pop("offset_mapping")
        labels = torch.full(offsets.shape[:2], -100, dtype=torch.long)
        for row, example in enumerate(group):
            for token_index, (start, end) in enumerate(offsets[row].tolist()):
                if start == end:
                    continue
                labels[row, token_index] = LABEL_O
                for mention_start, mention_end in example.spans:
                    if start < mention_end and end > mention_start:
                        labels[row, token_index] = (
                            LABEL_B if start == mention_start else LABEL_I
                        )
                        break
        return encoded, offsets, labels

    mention_history = []
    mention_rng = random.Random(args.seed)
    mention_model.train()
    for epoch in range(args.mention_epochs):
        total = 0.0
        seen = 0
        for group in batches(train, args.batch_size, mention_rng):
            encoded, _, labels = encode_mentions(group)
            mention_optimizer.zero_grad(set_to_none=True)
            logits = mention_model(
                encoded["input_ids"], encoded["attention_mask"], encoded.get("token_type_ids")
            )
            loss = mention_loss(logits.reshape(-1, 3), labels.reshape(-1))
            loss.backward()
            mention_optimizer.step()
            total += float(loss.detach()) * len(group)
            seen += len(group)
        avg = total / seen
        mention_history.append(avg)
        print(f"mention_epoch={epoch+1} average_loss={avg:.6f}")

    def decode_spans(labels, offsets, attention):
        spans = []
        current_start = current_end = None
        for label, (start, end), mask in zip(
            labels.tolist(), offsets.tolist(), attention.tolist()
        ):
            if not mask or start == end:
                continue
            if label == LABEL_B:
                if current_start is not None:
                    spans.append((current_start, current_end))
                current_start, current_end = start, end
            elif label == LABEL_I:
                if current_start is None:
                    current_start, current_end = start, end
                else:
                    current_end = end
            else:
                if current_start is not None:
                    spans.append((current_start, current_end))
                    current_start = current_end = None
        if current_start is not None:
            spans.append((current_start, current_end))
        return tuple(spans)

    # ------------------------------------------------------------------
    # Stage 2: gold-slotted text -> atomic relation/effect probes.
    # ------------------------------------------------------------------
    semantic_tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    semantic_tokenizer.add_special_tokens(
        {"additional_special_tokens": list(QUERY_TOKENS.values()) + [TARGET_TOKEN]}
    )
    semantic_backbone = AutoModel.from_pretrained(args.model)
    semantic_backbone.resize_token_embeddings(len(semantic_tokenizer))
    semantic_hidden = int(semantic_backbone.config.hidden_size)
    d = args.semantic_dim

    class SemanticProbe(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = semantic_backbone
            self.entity_key = nn.Linear(semantic_hidden, d, bias=False)
            self.source_query = nn.Linear(semantic_hidden, d, bias=False)
            self.destination_query = nn.Linear(semantic_hidden, d, bias=False)
            self.active_head = nn.Linear(semantic_hidden, 1)

        def forward(self, input_ids, attention_mask, entity_positions, entity_present, token_type_ids=None):
            kwargs = {"input_ids": input_ids, "attention_mask": attention_mask}
            if token_type_ids is not None:
                kwargs["token_type_ids"] = token_type_ids
            states = self.backbone(**kwargs).last_hidden_state
            pooled = states[:, 0]
            batch = states.shape[0]
            positions = entity_positions.clamp_min(0)
            entity_states = states[torch.arange(batch).unsqueeze(1), positions]
            keys = self.entity_key(entity_states)
            source_q = self.source_query(pooled)
            destination_q = self.destination_query(pooled)
            source_logits = torch.einsum("bd,bsd->bs", source_q, keys) / (d ** 0.5)
            destination_logits = torch.einsum("bd,bsd->bs", destination_q, keys) / (d ** 0.5)
            source_logits = source_logits.masked_fill(~entity_present, -1e9)
            destination_logits = destination_logits.masked_fill(~entity_present, -1e9)
            return self.active_head(pooled).squeeze(-1), source_logits, destination_logits

    semantic_model = SemanticProbe()
    semantic_head_params = [
        p for name, p in semantic_model.named_parameters() if not name.startswith("backbone.")
    ]
    semantic_optimizer = torch.optim.AdamW(
        [
            {"params": semantic_model.backbone.parameters(), "lr": args.backbone_lr},
            {"params": semantic_head_params, "lr": args.head_lr},
        ],
        weight_decay=0.01,
    )
    active_loss = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(3.0))
    pointer_loss = nn.CrossEntropyLoss()

    semantic_train_rows = tuple(
        (example.slotted, probe)
        for example in train
        for probe in probes_for(example.slotted)
    )

    def encode_probe_rows(rows):
        texts = [query_text(example, probe) for example, probe in rows]
        encoded = semantic_tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=112,
            return_tensors="pt",
            return_offsets_mapping=True,
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
        active = torch.tensor([probe.active for _, probe in rows], dtype=torch.float32)
        source = torch.tensor(
            [probe.source if probe.active else 0 for _, probe in rows], dtype=torch.long
        )
        destination = torch.tensor(
            [probe.destination if probe.active else 0 for _, probe in rows], dtype=torch.long
        )
        return encoded, positions, present, active, source, destination

    semantic_history = []
    semantic_rng = random.Random(args.seed + 1)
    semantic_model.train()
    for epoch in range(args.semantic_epochs):
        total = 0.0
        seen = 0
        for group in batches(semantic_train_rows, args.semantic_batch_size, semantic_rng):
            encoded, positions, present, active, source, destination = encode_probe_rows(group)
            semantic_optimizer.zero_grad(set_to_none=True)
            active_logits, source_logits, destination_logits = semantic_model(
                encoded["input_ids"],
                encoded["attention_mask"],
                positions,
                present,
                encoded.get("token_type_ids"),
            )
            loss = active_loss(active_logits, active)
            positive = active > 0.5
            if bool(positive.any()):
                loss = loss + pointer_loss(source_logits[positive], source[positive])
                loss = loss + pointer_loss(destination_logits[positive], destination[positive])
            loss.backward()
            semantic_optimizer.step()
            total += float(loss.detach()) * len(group)
            seen += len(group)
        avg = total / seen
        semantic_history.append(avg)
        print(f"semantic_epoch={epoch+1} average_loss={avg:.6f}")

    def predicted_patch(slotted_text: str, entities: tuple[str, ...]):
        if not 1 <= len(entities) <= MAX_SLOTS:
            return None
        # Reconstruct the lightweight DeltaExample shell expected by probes_for.
        # Its frame is irrelevant for inference; only slot enumeration is used.
        from compiler_delta_corpus import DeltaExample, DeltaFrame

        shell = DeltaExample(
            slotted_text,
            DeltaFrame(0, 0, 0, (0, 0, 0)),
            "inference",
            tuple((f"E{i}", entity) for i, entity in enumerate(entities)),
        )
        relation_deltas = []
        obligations = []
        rows = []
        metadata = []
        for subject in range(len(entities)):
            for relation_index, relation in enumerate(RELATIONS):
                # Build an inference probe directly, independent of a gold frame.
                from train_semantic_probe_compiler import Probe
                probe = Probe(relation, subject, 0, 0, 0)
                rows.append((shell, probe))
                metadata.append(("relation", subject, relation))
            from train_semantic_probe_compiler import Probe
            rows.append((shell, Probe("return", subject, 0, 0, 0)))
            metadata.append(("return", subject, "return"))

        encoded, positions, present, _, _, _ = encode_probe_rows(rows)
        with torch.no_grad():
            active_logits, source_logits, destination_logits = semantic_model(
                encoded["input_ids"],
                encoded["attention_mask"],
                positions,
                present,
                encoded.get("token_type_ids"),
            )
        active = (active_logits.sigmoid() >= 0.5).tolist()
        source = source_logits.argmax(dim=-1).tolist()
        destination = destination_logits.argmax(dim=-1).tolist()

        seen_cells = set()
        for i, (kind, subject, label) in enumerate(metadata):
            if not active[i]:
                continue
            src = int(source[i])
            dst = int(destination[i])
            if not (0 <= src < len(entities) and 0 <= dst < len(entities)):
                return None
            if kind == "relation":
                key = (subject, label)
                if key in seen_cells:
                    return None
                seen_cells.add(key)
                relation_deltas.append(
                    RelationDelta.build(
                        entities[subject], entities[src], entities[dst], (label,)
                    )
                )
            else:
                obligations.append(
                    ReturnObligation.build(entities[subject], entities[src], entities[dst])
                )
        if not relation_deltas and not obligations:
            return None
        try:
            return SemanticPatch.build(
                tuple(relation_deltas), return_obligations=tuple(obligations)
            )
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # End-to-end evaluation.
    # ------------------------------------------------------------------
    mention_model.eval()
    semantic_model.eval()
    mention_exact = 0
    semantic_gold_slot_exact = 0
    final_exact = 0
    rejected = 0
    family_final = defaultdict(lambda: {"exact": 0, "total": 0})
    mistakes = []

    with torch.no_grad():
        for start in range(0, len(evaluation), args.batch_size):
            group = list(evaluation[start:start + args.batch_size])
            encoded, offsets, _ = encode_mentions(group)
            logits = mention_model(
                encoded["input_ids"], encoded["attention_mask"], encoded.get("token_type_ids")
            )
            labels = logits.argmax(dim=-1)
            for row, example in enumerate(group):
                spans = decode_spans(labels[row], offsets[row], encoded["attention_mask"][row])
                spans_exact = set(spans) == set(example.spans)
                mention_exact += int(spans_exact)

                gold = gold_patch(example)
                gold_slot_patch = predicted_patch(example.slotted.text, example.mentions)
                semantic_gold_slot_exact += int(gold_slot_patch == gold)

                if not 1 <= len(spans) <= MAX_SLOTS:
                    predicted = None
                    rejected += 1
                    predicted_slotted = None
                else:
                    slotted = slotize_mentions(example.raw_text, spans)
                    predicted_slotted = slotted.text
                    predicted = predicted_patch(slotted.text, slotted.entities)
                    rejected += int(predicted is None)

                exact = predicted == gold
                final_exact += int(exact)
                family_final[example.family]["exact"] += int(exact)
                family_final[example.family]["total"] += 1
                if not exact and len(mistakes) < 32:
                    mistakes.append(
                        {
                            "raw_text": example.raw_text,
                            "family": example.family,
                            "gold_spans": list(example.spans),
                            "predicted_spans": list(spans),
                            "gold_slotted": example.slotted.text,
                            "predicted_slotted": predicted_slotted,
                            "gold_patch": repr(gold.transition_fingerprint()),
                            "predicted_patch": None
                            if predicted is None
                            else repr(predicted.transition_fingerprint()),
                            "mention_exact": spans_exact,
                            "gold_slot_semantic_exact": gold_slot_patch == gold,
                        }
                    )

    mention_params = sum(p.numel() for p in mention_model.parameters())
    semantic_params = sum(p.numel() for p in semantic_model.parameters())
    report = {
        "model": args.model,
        "mode": "raw_text_two_encoder_semantic_patch",
        "mention_parameters": mention_params,
        "semantic_parameters": semantic_params,
        "combined_parameters": mention_params + semantic_params,
        "train_samples": len(train),
        "eval_samples": len(evaluation),
        "mention_epochs": args.mention_epochs,
        "semantic_epochs": args.semantic_epochs,
        "mention_exact_sentence": mention_exact,
        "mention_exact_sentence_accuracy": mention_exact / len(evaluation),
        "semantic_exact_with_gold_mentions": semantic_gold_slot_exact,
        "semantic_exact_with_gold_mentions_accuracy": semantic_gold_slot_exact / len(evaluation),
        "end_to_end_exact_patch": final_exact,
        "end_to_end_exact_patch_accuracy": final_exact / len(evaluation),
        "pipeline_rejections": rejected,
        "family_final_exact": dict(family_final),
        "mention_loss_history": mention_history,
        "semantic_loss_history": semantic_history,
        "mistakes": mistakes,
        "caveat": "Initial integration benchmark: entity vocabulary is held out but sentence templates overlap train/eval. It tests raw pipeline composition, not unrestricted language generalization.",
    }
    Path("compiler-raw-end-to-end-results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in (
        "model", "mode", "mention_parameters", "semantic_parameters", "combined_parameters",
        "train_samples", "eval_samples", "mention_exact_sentence_accuracy",
        "semantic_exact_with_gold_mentions_accuracy", "end_to_end_exact_patch_accuracy",
        "pipeline_rejections", "family_final_exact", "mention_loss_history",
        "semantic_loss_history", "caveat"
    )}, indent=2))


if __name__ == "__main__":
    main()

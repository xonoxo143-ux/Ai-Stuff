from __future__ import annotations

import argparse
from collections import defaultdict
import json
import random
from pathlib import Path

from compiler_delta_corpus import DeltaExample, DeltaFrame
from compiler_raw_semantic_corpus import RawSemanticExample, generate_raw_semantic_examples
from train_raw_end_to_end import (
    LABEL_B,
    LABEL_I,
    LABEL_O,
    MAX_SLOTS,
    RELATIONS,
    gold_patch,
    marker_spans,
)
from train_semantic_probe_compiler import Probe, QUERY_TOKENS, TARGET_TOKEN, probes_for, query_text
from semzip.vm_delta import RelationDelta
from semzip.vm_mentions import slotize_mentions
from semzip.vm_patch import ReturnObligation, SemanticPatch


def batches(items, size, rng):
    indices = list(range(len(items)))
    rng.shuffle(indices)
    for start in range(0, len(indices), size):
        yield [items[i] for i in indices[start:start + size]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="google/bert_uncased_L-2_H-128_A-2")
    ap.add_argument("--train-samples", type=int, default=2048)
    ap.add_argument("--eval-samples", type=int, default=256)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--mention-batch-size", type=int, default=32)
    ap.add_argument("--semantic-batch-size", type=int, default=64)
    ap.add_argument("--semantic-rows-per-example", type=int, default=4)
    ap.add_argument("--backbone-lr", type=float, default=5e-5)
    ap.add_argument("--head-lr", type=float, default=5e-4)
    ap.add_argument("--semantic-dim", type=int, default=32)
    ap.add_argument("--seed", type=int, default=83)
    args = ap.parse_args()

    import torch
    import torch.nn as nn
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))

    train = generate_raw_semantic_examples(args.train_samples, split="train", seed=31)
    evaluation = generate_raw_semantic_examples(args.eval_samples, split="eval", seed=32)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    tokenizer.add_special_tokens(
        {"additional_special_tokens": list(QUERY_TOKENS.values()) + [TARGET_TOKEN]}
    )
    backbone = AutoModel.from_pretrained(args.model)
    backbone.resize_token_embeddings(len(tokenizer))
    hidden = int(backbone.config.hidden_size)
    d = args.semantic_dim

    class SharedFrontend(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = backbone
            self.mention_head = nn.Linear(hidden, 3)
            self.entity_key = nn.Linear(hidden, d, bias=False)
            self.source_query = nn.Linear(hidden, d, bias=False)
            self.destination_query = nn.Linear(hidden, d, bias=False)
            self.active_head = nn.Linear(hidden, 1)

        def states(self, input_ids, attention_mask, token_type_ids=None):
            kwargs = {"input_ids": input_ids, "attention_mask": attention_mask}
            if token_type_ids is not None:
                kwargs["token_type_ids"] = token_type_ids
            return self.backbone(**kwargs).last_hidden_state

        def mention(self, input_ids, attention_mask, token_type_ids=None):
            return self.mention_head(self.states(input_ids, attention_mask, token_type_ids))

        def semantic(
            self,
            input_ids,
            attention_mask,
            entity_positions,
            entity_present,
            token_type_ids=None,
        ):
            states = self.states(input_ids, attention_mask, token_type_ids)
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

    model = SharedFrontend()
    total_parameters = sum(p.numel() for p in model.parameters())
    backbone_parameters = sum(p.numel() for p in model.backbone.parameters())
    head_parameters = total_parameters - backbone_parameters
    head_params = [p for name, p in model.named_parameters() if not name.startswith("backbone.")]
    optimizer = torch.optim.AdamW(
        [
            {"params": model.backbone.parameters(), "lr": args.backbone_lr},
            {"params": head_params, "lr": args.head_lr},
        ],
        weight_decay=0.01,
    )
    mention_loss_fn = nn.CrossEntropyLoss(
        weight=torch.tensor([0.25, 1.0, 1.0]), ignore_index=-100
    )
    active_loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(3.0))
    pointer_loss_fn = nn.CrossEntropyLoss()

    def encode_mentions(group: list[RawSemanticExample]):
        texts = [x.raw_text for x in group]
        encoded = tokenizer(
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

    semantic_rows = tuple(
        (example.slotted, probe)
        for example in train
        for probe in probes_for(example.slotted)
    )

    def encode_probe_rows(rows):
        texts = [query_text(example, probe) for example, probe in rows]
        encoded = tokenizer(
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

    rng = random.Random(args.seed)
    mention_history = []
    semantic_history = []
    target_semantic_rows = min(
        len(semantic_rows), len(train) * max(args.semantic_rows_per_example, 1)
    )

    for epoch in range(args.epochs):
        model.train()
        mention_total = mention_seen = 0
        for group in batches(train, args.mention_batch_size, rng):
            encoded, _, labels = encode_mentions(group)
            optimizer.zero_grad(set_to_none=True)
            logits = model.mention(
                encoded["input_ids"], encoded["attention_mask"], encoded.get("token_type_ids")
            )
            loss = mention_loss_fn(logits.reshape(-1, 3), labels.reshape(-1))
            loss.backward()
            optimizer.step()
            mention_total += float(loss.detach()) * len(group)
            mention_seen += len(group)

        selected = list(semantic_rows)
        rng.shuffle(selected)
        selected = selected[:target_semantic_rows]
        semantic_total = semantic_seen = 0
        for group in batches(selected, args.semantic_batch_size, rng):
            encoded, positions, present, active, source, destination = encode_probe_rows(group)
            optimizer.zero_grad(set_to_none=True)
            active_logits, source_logits, destination_logits = model.semantic(
                encoded["input_ids"],
                encoded["attention_mask"],
                positions,
                present,
                encoded.get("token_type_ids"),
            )
            loss = active_loss_fn(active_logits, active)
            positive = active > 0.5
            if bool(positive.any()):
                loss = loss + pointer_loss_fn(source_logits[positive], source[positive])
                loss = loss + pointer_loss_fn(destination_logits[positive], destination[positive])
            loss.backward()
            optimizer.step()
            semantic_total += float(loss.detach()) * len(group)
            semantic_seen += len(group)

        mention_avg = mention_total / max(mention_seen, 1)
        semantic_avg = semantic_total / max(semantic_seen, 1)
        mention_history.append(mention_avg)
        semantic_history.append(semantic_avg)
        print(
            f"epoch={epoch+1} mention_loss={mention_avg:.6f} "
            f"semantic_loss={semantic_avg:.6f} semantic_rows={semantic_seen}"
        )

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

    def predict_patch(slotted_text: str, entities: tuple[str, ...]):
        if not 1 <= len(entities) <= MAX_SLOTS:
            return None
        shell = DeltaExample(
            slotted_text,
            DeltaFrame(0, 0, 0, (0, 0, 0)),
            "inference",
            tuple((f"E{i}", entity) for i, entity in enumerate(entities)),
        )
        rows = []
        metadata = []
        for subject in range(len(entities)):
            for relation in RELATIONS:
                rows.append((shell, Probe(relation, subject, 0, 0, 0)))
                metadata.append(("relation", subject, relation))
            rows.append((shell, Probe("return", subject, 0, 0, 0)))
            metadata.append(("return", subject, "return"))
        encoded, positions, present, _, _, _ = encode_probe_rows(rows)
        with torch.no_grad():
            active_logits, source_logits, destination_logits = model.semantic(
                encoded["input_ids"],
                encoded["attention_mask"],
                positions,
                present,
                encoded.get("token_type_ids"),
            )
        active = (active_logits.sigmoid() >= 0.5).tolist()
        source = source_logits.argmax(-1).tolist()
        destination = destination_logits.argmax(-1).tolist()
        deltas = []
        obligations = []
        for index, (kind, subject, label) in enumerate(metadata):
            if not active[index]:
                continue
            src = int(source[index])
            dst = int(destination[index])
            if not (0 <= src < len(entities) and 0 <= dst < len(entities)):
                return None
            if kind == "relation":
                deltas.append(
                    RelationDelta.build(entities[subject], entities[src], entities[dst], (label,))
                )
            else:
                obligations.append(
                    ReturnObligation.build(entities[subject], entities[src], entities[dst])
                )
        if not deltas and not obligations:
            return None
        try:
            return SemanticPatch.build(tuple(deltas), return_obligations=tuple(obligations))
        except ValueError:
            return None

    model.eval()
    mention_exact = semantic_gold_exact = final_exact = rejected = 0
    family = defaultdict(lambda: {"exact": 0, "total": 0})
    mistakes = []
    with torch.no_grad():
        for start in range(0, len(evaluation), args.mention_batch_size):
            group = list(evaluation[start:start + args.mention_batch_size])
            encoded, offsets, _ = encode_mentions(group)
            logits = model.mention(
                encoded["input_ids"], encoded["attention_mask"], encoded.get("token_type_ids")
            )
            predictions = logits.argmax(-1)
            for row, example in enumerate(group):
                spans = decode_spans(
                    predictions[row], offsets[row], encoded["attention_mask"][row]
                )
                span_exact = set(spans) == set(example.spans)
                mention_exact += int(span_exact)
                gold = gold_patch(example)
                gold_semantic = predict_patch(example.slotted.text, example.mentions)
                semantic_gold_exact += int(gold_semantic == gold)

                if not 1 <= len(spans) <= MAX_SLOTS:
                    predicted = None
                    rejected += 1
                    predicted_slotted = None
                else:
                    slotted = slotize_mentions(example.raw_text, spans)
                    predicted_slotted = slotted.text
                    predicted = predict_patch(slotted.text, slotted.entities)
                    rejected += int(predicted is None)
                exact = predicted == gold
                final_exact += int(exact)
                family[example.family]["exact"] += int(exact)
                family[example.family]["total"] += 1
                if not exact and len(mistakes) < 32:
                    mistakes.append(
                        {
                            "raw_text": example.raw_text,
                            "family": example.family,
                            "gold_spans": list(example.spans),
                            "predicted_spans": list(spans),
                            "gold_slotted": example.slotted.text,
                            "predicted_slotted": predicted_slotted,
                            "mention_exact": span_exact,
                            "gold_slot_semantic_exact": gold_semantic == gold,
                        }
                    )

    report = {
        "model": args.model,
        "mode": "raw_text_shared_tiny_encoder",
        "total_parameters": total_parameters,
        "backbone_parameters": backbone_parameters,
        "head_parameters": head_parameters,
        "train_samples": len(train),
        "eval_samples": len(evaluation),
        "epochs": args.epochs,
        "semantic_rows_per_epoch": target_semantic_rows,
        "mention_exact_sentence_accuracy": mention_exact / len(evaluation),
        "semantic_exact_with_gold_mentions_accuracy": semantic_gold_exact / len(evaluation),
        "end_to_end_exact_patch_accuracy": final_exact / len(evaluation),
        "pipeline_rejections": rejected,
        "family_final_exact": dict(family),
        "mention_loss_history": mention_history,
        "semantic_loss_history": semantic_history,
        "mistakes": mistakes,
        "caveat": "Shared-backbone integration benchmark with held-out entities but overlapping sentence templates; not unrestricted language generalization.",
    }
    Path("compiler-raw-shared-results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in (
        "model", "mode", "total_parameters", "backbone_parameters", "head_parameters",
        "train_samples", "eval_samples", "epochs", "semantic_rows_per_epoch",
        "mention_exact_sentence_accuracy", "semantic_exact_with_gold_mentions_accuracy",
        "end_to_end_exact_patch_accuracy", "pipeline_rejections", "family_final_exact",
        "mention_loss_history", "semantic_loss_history", "caveat"
    )}, indent=2))


if __name__ == "__main__":
    main()

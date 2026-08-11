from __future__ import annotations

import argparse
from collections import defaultdict
import json
import random
import re
from pathlib import Path

from compiler_delta_corpus import MAX_SLOTS, NONE_SLOT, DeltaExample, generate_delta_examples


def batches(items, size, rng):
    indices = list(range(len(items)))
    rng.shuffle(indices)
    for start in range(0, len(indices), size):
        yield [items[i] for i in indices[start : start + size]]


def frame_targets(example: DeltaExample):
    f = example.frame
    return (
        (
            f.primary_subject, f.primary_source, f.primary_destination,
            f.secondary_subject, f.secondary_source, f.secondary_destination,
        ),
        (
            *f.primary_relations, *f.secondary_relations,
            f.secondary_present, f.return_obligation,
        ),
    )


def marker_spans(text: str):
    spans = {}
    for slot in range(MAX_SLOTS):
        match = re.search(rf"(?<![A-Za-z0-9_])E{slot}(?![A-Za-z0-9_])", text)
        if match:
            spans[slot] = match.span()
    return spans


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google/bert_uncased_L-2_H-128_A-2")
    parser.add_argument("--train-samples", type=int, default=512)
    parser.add_argument("--eval-samples", type=int, default=96)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--backbone-lr", type=float, default=5e-5)
    parser.add_argument("--head-lr", type=float, default=5e-4)
    parser.add_argument("--pointer-dim", type=int, default=32)
    parser.add_argument("--seed", type=int, default=37)
    args = parser.parse_args()

    import torch
    import torch.nn as nn
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))

    # Exactly the same baseline semantic distribution used by the 135M/360M tests.
    train = generate_delta_examples(args.train_samples, split="train", seed=23)
    evaluation = generate_delta_examples(args.eval_samples, split="eval", seed=24)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("tiny encoder pointer benchmark requires tokenizer offsets")

    backbone = AutoModel.from_pretrained(args.model)
    hidden = int(backbone.config.hidden_size)
    d = args.pointer_dim

    class TinyEncoderDeltaCompiler(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = backbone
            self.entity_projection = nn.Linear(hidden, d, bias=False)
            self.role_queries = nn.Linear(hidden, 6 * d, bias=True)
            self.none_head = nn.Linear(hidden, 6, bias=True)
            self.bit_head = nn.Linear(hidden, 8)

        def forward(self, input_ids, attention_mask, entity_positions, entity_present, token_type_ids=None):
            kwargs = {"input_ids": input_ids, "attention_mask": attention_mask}
            if token_type_ids is not None:
                kwargs["token_type_ids"] = token_type_ids
            outputs = self.backbone(**kwargs)
            states = outputs.last_hidden_state
            # BERT's CLS state and every entity marker are bidirectional: each can
            # incorporate evidence from both left and right context.
            pooled = states[:, 0]
            batch = states.shape[0]
            safe_positions = entity_positions.clamp_min(0)
            entity_states = states[torch.arange(batch).unsqueeze(1), safe_positions]
            entity_vectors = self.entity_projection(entity_states)
            role_vectors = self.role_queries(pooled).view(batch, 6, d)
            logits = torch.einsum("brd,bsd->brs", role_vectors, entity_vectors) / (d ** 0.5)
            logits = logits.masked_fill(~entity_present.unsqueeze(1), -1e9)
            pointer_logits = torch.cat((logits, self.none_head(pooled).unsqueeze(-1)), dim=-1)
            return pointer_logits, self.bit_head(pooled)

    model = TinyEncoderDeltaCompiler()
    total_parameters = sum(p.numel() for p in model.parameters())
    backbone_parameters = sum(p.numel() for p in model.backbone.parameters())
    head_parameters = total_parameters - backbone_parameters

    head_params = []
    for module in (model.entity_projection, model.role_queries, model.none_head, model.bit_head):
        head_params.extend(module.parameters())
    optimizer = torch.optim.AdamW(
        [
            {"params": model.backbone.parameters(), "lr": args.backbone_lr},
            {"params": head_params, "lr": args.head_lr},
        ],
        weight_decay=0.01,
    )
    pointer_loss = nn.CrossEntropyLoss()
    bit_loss = nn.BCEWithLogitsLoss()
    rng = random.Random(args.seed)

    def encode(group: list[DeltaExample]):
        texts = [x.text for x in group]
        encoded = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=96,
            return_tensors="pt",
            return_offsets_mapping=True,
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
        pointers, bits = zip(*(frame_targets(x) for x in group))
        return (
            encoded,
            positions,
            present,
            torch.tensor(pointers, dtype=torch.long),
            torch.tensor(bits, dtype=torch.float32),
        )

    loss_history = []
    model.train()
    for epoch in range(args.epochs):
        total_loss = 0.0
        seen = 0
        for group in batches(train, args.batch_size, rng):
            encoded, positions, present, pointers, bits = encode(group)
            optimizer.zero_grad(set_to_none=True)
            pointer_logits, bit_logits = model(
                encoded["input_ids"],
                encoded["attention_mask"],
                positions,
                present,
                encoded.get("token_type_ids"),
            )
            # Keep the original baseline objective for a clean architecture comparison:
            # all six pointer roles are supervised, including explicit NONE targets.
            loss = bit_loss(bit_logits, bits)
            for position in range(6):
                loss = loss + pointer_loss(pointer_logits[:, position, :], pointers[:, position])
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(group)
            seen += len(group)
        average = total_loss / max(seen, 1)
        loss_history.append(average)
        print(f"epoch={epoch + 1} average_loss={average:.6f}")

    model.eval()
    pointer_correct = pointer_total = bit_correct = bit_total = strict_exact = resolved_exact = 0
    family_strict = defaultdict(lambda: {"exact": 0, "total": 0})
    family_resolved = defaultdict(lambda: {"exact": 0, "total": 0})
    mistakes = []

    with torch.no_grad():
        for start in range(0, len(evaluation), args.batch_size):
            group = list(evaluation[start:start + args.batch_size])
            encoded, positions, present, gold_pointers, gold_bits = encode(group)
            pointer_logits, bit_logits = model(
                encoded["input_ids"],
                encoded["attention_mask"],
                positions,
                present,
                encoded.get("token_type_ids"),
            )
            pred_pointers = pointer_logits.argmax(dim=-1)
            pred_bits = (bit_logits.sigmoid() >= 0.5).to(torch.long)
            gold_bits_i = gold_bits.to(torch.long)

            for row, example in enumerate(group):
                pp = tuple(int(x) for x in pred_pointers[row].tolist())
                gp = tuple(int(x) for x in gold_pointers[row].tolist())
                pb = tuple(int(x) for x in pred_bits[row].tolist())
                gb = tuple(int(x) for x in gold_bits_i[row].tolist())
                pointer_correct += sum(int(a == b) for a, b in zip(pp, gp))
                pointer_total += len(gp)
                bit_correct += sum(int(a == b) for a, b in zip(pb, gb))
                bit_total += len(gb)

                strict = pp == gp and pb == gb
                strict_exact += int(strict)
                family_strict[example.family]["exact"] += int(strict)
                family_strict[example.family]["total"] += 1

                # Runtime can deterministically clear an absent secondary payload once
                # the secondary-present bit says there is no second transition.
                resolved_pp = list(pp)
                resolved_pb = list(pb)
                if resolved_pb[6] == 0:
                    resolved_pp[3:6] = [NONE_SLOT, NONE_SLOT, NONE_SLOT]
                    resolved_pb[3:6] = [0, 0, 0]
                resolved = tuple(resolved_pp) == gp and tuple(resolved_pb) == gb
                resolved_exact += int(resolved)
                family_resolved[example.family]["exact"] += int(resolved)
                family_resolved[example.family]["total"] += 1

                if not resolved and len(mistakes) < 24:
                    mistakes.append({
                        "text": example.text,
                        "family": example.family,
                        "gold_pointers": list(gp),
                        "predicted_pointers": list(pp),
                        "gold_bits": list(gb),
                        "predicted_bits": list(pb),
                        "slots": list(example.slots),
                    })

    report = {
        "model": args.model,
        "mode": "tiny_bidirectional_context_pointer_delta",
        "pointer_dim": d,
        "train_samples": len(train),
        "eval_samples": len(evaluation),
        "epochs": args.epochs,
        "total_parameters": total_parameters,
        "backbone_parameters": backbone_parameters,
        "head_parameters": head_parameters,
        "trainable_parameters": total_parameters,
        "pointer_accuracy": pointer_correct / pointer_total,
        "bit_accuracy": bit_correct / bit_total,
        "strict_exact_frame": strict_exact,
        "strict_exact_accuracy": strict_exact / len(evaluation),
        "resolved_exact_frame": resolved_exact,
        "resolved_exact_accuracy": resolved_exact / len(evaluation),
        "family_strict": dict(family_strict),
        "family_resolved": dict(family_resolved),
        "loss_history": loss_history,
        "mistakes": mistakes,
        "contract": {
            "bidirectional_encoder": True,
            "full_backbone_finetune": True,
            "contextual_entity_pointer_keys": True,
            "full_sentence_role_queries": True,
            "free_form_generation": False,
            "lexical_action_classes": False,
        },
    }
    Path("compiler-tinybert-delta-results.json").write_text(json.dumps(report, indent=2))
    output = Path("semvm-tinybert-delta-compiler")
    output.mkdir(exist_ok=True)
    model.backbone.save_pretrained(output)
    tokenizer.save_pretrained(output)
    torch.save(
        {
            "entity_projection": model.entity_projection.state_dict(),
            "role_queries": model.role_queries.state_dict(),
            "none_head": model.none_head.state_dict(),
            "bit_head": model.bit_head.state_dict(),
            "hidden_size": hidden,
            "pointer_dim": d,
        },
        output / "semantic_heads.pt",
    )

    print(json.dumps({k: report[k] for k in (
        "model", "mode", "total_parameters", "backbone_parameters", "head_parameters",
        "train_samples", "eval_samples", "epochs", "pointer_accuracy", "bit_accuracy",
        "strict_exact_frame", "strict_exact_accuracy", "resolved_exact_frame",
        "resolved_exact_accuracy", "family_strict", "family_resolved", "loss_history"
    )}, indent=2))


if __name__ == "__main__":
    main()

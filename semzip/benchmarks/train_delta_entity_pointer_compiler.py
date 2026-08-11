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
    parser.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M-Instruct")
    parser.add_argument("--train-samples", type=int, default=512)
    parser.add_argument("--eval-samples", type=int, default=96)
    parser.add_argument("--epochs", type=int, default=7)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=29)
    args = parser.parse_args()

    import torch
    import torch.nn as nn
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))

    train = generate_delta_examples(args.train_samples, split="train", seed=23)
    evaluation = generate_delta_examples(args.eval_samples, split="eval", seed=24)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("entity pointer benchmark requires a fast tokenizer with offsets")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    backbone = AutoModel.from_pretrained(args.model)
    backbone.config.use_cache = False
    lora = LoraConfig(
        r=4, lora_alpha=8, lora_dropout=0.0,
        target_modules=["q_proj", "v_proj"], bias="none",
        task_type=TaskType.FEATURE_EXTRACTION,
    )
    backbone = get_peft_model(backbone, lora)
    hidden = int(backbone.config.hidden_size)

    class EntityPointerDeltaCompiler(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = backbone
            # Each semantic pointer role is a learned query over contextual entity states.
            self.role_queries = nn.Parameter(torch.empty(6, hidden))
            nn.init.normal_(self.role_queries, std=hidden ** -0.5)
            self.none_logits = nn.Parameter(torch.zeros(6))
            self.bit_head = nn.Linear(hidden, 8)

        def forward(self, input_ids, attention_mask, entity_positions, entity_present):
            outputs = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
            states = outputs.last_hidden_state
            batch = states.shape[0]
            safe_positions = entity_positions.clamp_min(0)
            entity_states = states[
                torch.arange(batch).unsqueeze(1),
                safe_positions,
            ]  # [B, 4, H]
            # Contextual entity representations already encode surrounding syntax.
            logits = torch.einsum("bsh,rh->brs", entity_states, self.role_queries)
            logits = logits.masked_fill(~entity_present.unsqueeze(1), -1e9)
            none = self.none_logits.view(1, 6, 1).expand(batch, -1, -1)
            pointer_logits = torch.cat((logits, none), dim=-1)  # [B, 6, 5]

            last_index = attention_mask.sum(dim=1) - 1
            pooled = states[torch.arange(batch), last_index]
            bit_logits = self.bit_head(pooled)
            return pointer_logits, bit_logits

    model = EntityPointerDeltaCompiler()
    total_parameters = sum(p.numel() for p in model.parameters())
    trainable_parameters = sum(p.numel() for p in model.parameters() if p.requires_grad)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.lr)
    pointer_loss = nn.CrossEntropyLoss()
    bit_loss = nn.BCEWithLogitsLoss()
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
            spans = marker_spans(text)
            for slot, (char_start, char_end) in spans.items():
                for token_index, pair in enumerate(offsets[row].tolist()):
                    start, end = pair
                    if start < char_end and end > char_start:
                        positions[row, slot] = token_index
                        present[row, slot] = True
                        break
                if not present[row, slot]:
                    raise RuntimeError(f"could not map E{slot} to tokenizer offsets in {text!r}")
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
                encoded["input_ids"], encoded["attention_mask"], positions, present
            )
            loss = bit_loss(bit_logits, bits)
            for position in range(3):
                loss = loss + pointer_loss(pointer_logits[:, position, :], pointers[:, position])
            secondary_mask = bits[:, 6] > 0.5
            if bool(secondary_mask.any()):
                for position in range(3, 6):
                    loss = loss + pointer_loss(
                        pointer_logits[secondary_mask, position, :],
                        pointers[secondary_mask, position],
                    )
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(group)
            seen += len(group)
        average = total_loss / max(seen, 1)
        loss_history.append(average)
        print(f"epoch={epoch + 1} average_loss={average:.6f}")

    model.eval()
    pointer_correct = pointer_total = bit_correct = bit_total = exact = 0
    family_exact = defaultdict(lambda: {"exact": 0, "total": 0})
    mistakes = []
    with torch.no_grad():
        for start in range(0, len(evaluation), args.batch_size):
            group = list(evaluation[start:start + args.batch_size])
            encoded, positions, present, gold_pointers, gold_bits = encode(group)
            pointer_logits, bit_logits = model(
                encoded["input_ids"], encoded["attention_mask"], positions, present
            )
            pred_pointers = pointer_logits.argmax(dim=-1)
            pred_bits = (bit_logits.sigmoid() >= 0.5).to(torch.long)
            gold_bits_i = gold_bits.to(torch.long)
            for row in range(len(group)):
                if int(pred_bits[row, 6]) == 0:
                    pred_pointers[row, 3:6] = NONE_SLOT
                    pred_bits[row, 3:6] = 0
            for row, example in enumerate(group):
                pp = tuple(int(x) for x in pred_pointers[row].tolist())
                gp = tuple(int(x) for x in gold_pointers[row].tolist())
                pb = tuple(int(x) for x in pred_bits[row].tolist())
                gb = tuple(int(x) for x in gold_bits_i[row].tolist())
                pointer_correct += sum(int(a == b) for a, b in zip(pp, gp))
                pointer_total += len(gp)
                bit_correct += sum(int(a == b) for a, b in zip(pb, gb))
                bit_total += len(gb)
                is_exact = pp == gp and pb == gb
                exact += int(is_exact)
                family_exact[example.family]["exact"] += int(is_exact)
                family_exact[example.family]["total"] += 1
                if not is_exact and len(mistakes) < 24:
                    mistakes.append({
                        "text": example.text, "family": example.family,
                        "gold_pointers": list(gp), "predicted_pointers": list(pp),
                        "gold_bits": list(gb), "predicted_bits": list(pb),
                        "slots": list(example.slots),
                    })

    report = {
        "model": args.model,
        "mode": "contextual_entity_pointer_delta",
        "train_samples": len(train), "eval_samples": len(evaluation),
        "epochs": args.epochs, "total_parameters": total_parameters,
        "trainable_parameters": trainable_parameters,
        "pointer_accuracy": pointer_correct / pointer_total,
        "bit_accuracy": bit_correct / bit_total,
        "exact_frame": exact, "exact_frame_accuracy": exact / len(evaluation),
        "family_exact": dict(family_exact), "loss_history": loss_history,
        "mistakes": mistakes,
        "contract": {
            "entity_pointer_scores_contextual_marker_states": True,
            "secondary_pointer_loss_masked_when_absent": True,
            "free_form_generation": False,
            "lexical_action_classes": False,
        },
    }
    Path("compiler-delta-entity-pointer-results.json").write_text(json.dumps(report, indent=2))
    Path("semvm-delta-entity-pointer-adapter").mkdir(exist_ok=True)
    model.backbone.save_pretrained("semvm-delta-entity-pointer-adapter")
    torch.save({
        "role_queries": model.role_queries.detach().cpu(),
        "none_logits": model.none_logits.detach().cpu(),
        "bit_head": model.bit_head.state_dict(),
        "hidden_size": hidden,
    }, "semvm-delta-entity-pointer-adapter/pointer_heads.pt")

    print(f"model={args.model} total_parameters={total_parameters} trainable_parameters={trainable_parameters}")
    print(json.dumps({k: report[k] for k in (
        "mode", "train_samples", "eval_samples", "epochs", "trainable_parameters",
        "pointer_accuracy", "bit_accuracy", "exact_frame", "exact_frame_accuracy",
        "family_exact", "loss_history"
    )}, indent=2))


if __name__ == "__main__":
    main()

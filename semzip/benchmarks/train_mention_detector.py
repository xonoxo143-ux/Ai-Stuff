from __future__ import annotations

import argparse
from collections import defaultdict
import json
import random
from pathlib import Path

from compiler_mention_corpus import MentionExample, generate_mention_examples
from semzip.vm_mentions import slotize_mentions


LABEL_O = 0
LABEL_B = 1
LABEL_I = 2


def batches(items, size, rng):
    indices = list(range(len(items)))
    rng.shuffle(indices)
    for start in range(0, len(indices), size):
        yield [items[i] for i in indices[start:start + size]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google/bert_uncased_L-2_H-128_A-2")
    parser.add_argument("--train-samples", type=int, default=2048)
    parser.add_argument("--eval-samples", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--backbone-lr", type=float, default=5e-5)
    parser.add_argument("--head-lr", type=float, default=5e-4)
    parser.add_argument("--seed", type=int, default=71)
    args = parser.parse_args()

    import torch
    import torch.nn as nn
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))

    train = generate_mention_examples(args.train_samples, split="train", seed=17)
    evaluation = generate_mention_examples(args.eval_samples, split="eval", seed=18)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("mention detector requires a fast tokenizer with offsets")
    backbone = AutoModel.from_pretrained(args.model)
    hidden = int(backbone.config.hidden_size)

    class MentionDetector(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = backbone
            self.head = nn.Linear(hidden, 3)

        def forward(self, input_ids, attention_mask, token_type_ids=None):
            kwargs = {"input_ids": input_ids, "attention_mask": attention_mask}
            if token_type_ids is not None:
                kwargs["token_type_ids"] = token_type_ids
            states = self.backbone(**kwargs).last_hidden_state
            return self.head(states)

    model = MentionDetector()
    total_parameters = sum(p.numel() for p in model.parameters())
    backbone_parameters = sum(p.numel() for p in model.backbone.parameters())
    head_parameters = total_parameters - backbone_parameters
    optimizer = torch.optim.AdamW(
        [
            {"params": model.backbone.parameters(), "lr": args.backbone_lr},
            {"params": model.head.parameters(), "lr": args.head_lr},
        ],
        weight_decay=0.01,
    )
    loss_fn = nn.CrossEntropyLoss(
        weight=torch.tensor([0.25, 1.0, 1.0]),
        ignore_index=-100,
    )
    rng = random.Random(args.seed)

    def encode(group: list[MentionExample]):
        texts = [x.text for x in group]
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

    loss_history = []
    model.train()
    for epoch in range(args.epochs):
        total_loss = 0.0
        seen = 0
        for group in batches(train, args.batch_size, rng):
            encoded, _, labels = encode(group)
            optimizer.zero_grad(set_to_none=True)
            logits = model(
                encoded["input_ids"],
                encoded["attention_mask"],
                encoded.get("token_type_ids"),
            )
            loss = loss_fn(logits.reshape(-1, 3), labels.reshape(-1))
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(group)
            seen += len(group)
        average = total_loss / max(seen, 1)
        loss_history.append(average)
        print(f"epoch={epoch + 1} average_loss={average:.6f}")

    def decode_spans(predictions, offsets, attention):
        spans = []
        current_start = current_end = None
        for label, (start, end), mask in zip(
            predictions.tolist(), offsets.tolist(), attention.tolist()
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

    tp = fp = fn = 0
    exact_sentences = 0
    exact_slotization = 0
    family_exact = defaultdict(lambda: {"exact": 0, "total": 0})
    mistakes = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(evaluation), args.batch_size):
            group = list(evaluation[start:start + args.batch_size])
            encoded, offsets, _ = encode(group)
            logits = model(
                encoded["input_ids"],
                encoded["attention_mask"],
                encoded.get("token_type_ids"),
            )
            predictions = logits.argmax(dim=-1)
            for row, example in enumerate(group):
                predicted = decode_spans(
                    predictions[row], offsets[row], encoded["attention_mask"][row]
                )
                gold = tuple(example.spans)
                predicted_set = set(predicted)
                gold_set = set(gold)
                tp += len(predicted_set & gold_set)
                fp += len(predicted_set - gold_set)
                fn += len(gold_set - predicted_set)
                exact = predicted_set == gold_set
                exact_sentences += int(exact)
                family_exact[example.family]["exact"] += int(exact)
                family_exact[example.family]["total"] += 1

                predicted_slot = slotize_mentions(example.text, predicted).text
                gold_slot = slotize_mentions(example.text, gold).text
                slot_exact = predicted_slot == gold_slot
                exact_slotization += int(slot_exact)
                if not exact and len(mistakes) < 24:
                    mistakes.append(
                        {
                            "text": example.text,
                            "family": example.family,
                            "gold_spans": list(gold),
                            "predicted_spans": list(predicted),
                            "gold_mentions": [example.text[a:b] for a, b in gold],
                            "predicted_mentions": [example.text[a:b] for a, b in predicted],
                            "gold_slotted": gold_slot,
                            "predicted_slotted": predicted_slot,
                        }
                    )

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    report = {
        "model": args.model,
        "mode": "semantic_mention_bio",
        "total_parameters": total_parameters,
        "backbone_parameters": backbone_parameters,
        "head_parameters": head_parameters,
        "train_samples": len(train),
        "eval_samples": len(evaluation),
        "epochs": args.epochs,
        "mention_precision": precision,
        "mention_recall": recall,
        "mention_f1": f1,
        "exact_span_sentences": exact_sentences,
        "exact_span_sentence_accuracy": exact_sentences / len(evaluation),
        "exact_slotization": exact_slotization,
        "exact_slotization_accuracy": exact_slotization / len(evaluation),
        "family_exact": dict(family_exact),
        "loss_history": loss_history,
        "mistakes": mistakes,
    }
    Path("compiler-mention-results.json").write_text(json.dumps(report, indent=2))
    output = Path("semvm-mention-detector")
    output.mkdir(exist_ok=True)
    model.backbone.save_pretrained(output)
    tokenizer.save_pretrained(output)
    torch.save(model.head.state_dict(), output / "mention_head.pt")
    print(json.dumps({k: report[k] for k in (
        "model", "mode", "total_parameters", "head_parameters", "train_samples",
        "eval_samples", "epochs", "mention_precision", "mention_recall", "mention_f1",
        "exact_span_sentence_accuracy", "exact_slotization_accuracy", "family_exact",
        "loss_history"
    )}, indent=2))


if __name__ == "__main__":
    main()

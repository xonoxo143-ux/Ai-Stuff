from __future__ import annotations

import argparse
from collections import defaultdict
import json
import random
from pathlib import Path

from compiler_structured_corpus import (
    MAX_SLOTS,
    NONE_SLOT,
    OPERATION_NAMES,
    StructuredExample,
    generate_structured_examples,
)


def batches(items, size, rng):
    indices = list(range(len(items)))
    rng.shuffle(indices)
    for start in range(0, len(indices), size):
        yield [items[i] for i in indices[start : start + size]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M-Instruct")
    parser.add_argument("--train-samples", type=int, default=256)
    parser.add_argument("--eval-samples", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()

    import torch
    import torch.nn as nn
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))

    train = generate_structured_examples(args.train_samples, split="train", seed=args.seed)
    evaluation = generate_structured_examples(args.eval_samples, split="eval", seed=args.seed + 1)

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    backbone = AutoModel.from_pretrained(args.model)
    backbone.config.use_cache = False
    lora = LoraConfig(
        r=4,
        lora_alpha=8,
        lora_dropout=0.0,
        target_modules=["q_proj", "v_proj"],
        bias="none",
        task_type=TaskType.FEATURE_EXTRACTION,
    )
    backbone = get_peft_model(backbone, lora)
    hidden = int(backbone.config.hidden_size)

    class StructuredCompiler(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = backbone
            self.operation_head = nn.Linear(hidden, len(OPERATION_NAMES))
            self.argument_head = nn.Linear(hidden, 4 * (MAX_SLOTS + 1))

        def forward(self, input_ids, attention_mask):
            outputs = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
            states = outputs.last_hidden_state
            # Inputs are right-padded. The final real token has seen the whole sentence.
            last_index = attention_mask.sum(dim=1) - 1
            pooled = states[torch.arange(states.shape[0]), last_index]
            op_logits = self.operation_head(pooled)
            arg_logits = self.argument_head(pooled).view(-1, 4, MAX_SLOTS + 1)
            return op_logits, arg_logits

    model = StructuredCompiler()
    total_parameters = sum(p.numel() for p in model.parameters())
    trainable_parameters = sum(p.numel() for p in model.parameters() if p.requires_grad)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.lr)
    operation_loss = nn.CrossEntropyLoss()
    argument_loss = nn.CrossEntropyLoss()
    rng = random.Random(args.seed)

    def encode(group: list[StructuredExample]):
        encoded = tokenizer(
            [x.text for x in group],
            padding=True,
            truncation=True,
            max_length=96,
            return_tensors="pt",
        )
        operations = torch.tensor([x.operation for x in group], dtype=torch.long)
        arguments = torch.tensor([x.args for x in group], dtype=torch.long)
        return encoded, operations, arguments

    loss_history: list[float] = []
    model.train()
    for epoch in range(args.epochs):
        total_loss = 0.0
        seen = 0
        for group in batches(train, args.batch_size, rng):
            encoded, operations, arguments = encode(group)
            optimizer.zero_grad(set_to_none=True)
            op_logits, arg_logits = model(encoded["input_ids"], encoded["attention_mask"])
            loss = operation_loss(op_logits, operations)
            for position in range(4):
                loss = loss + argument_loss(arg_logits[:, position, :], arguments[:, position])
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(group)
            seen += len(group)
        average = total_loss / max(seen, 1)
        loss_history.append(average)
        print(f"epoch={epoch + 1} average_loss={average:.6f}")

    model.eval()
    op_correct = 0
    arg_correct = 0
    arg_total = 0
    exact = 0
    family_exact = defaultdict(lambda: {"exact": 0, "total": 0})
    mistakes = []

    with torch.no_grad():
        for start in range(0, len(evaluation), args.batch_size):
            group = list(evaluation[start : start + args.batch_size])
            encoded, operations, arguments = encode(group)
            op_logits, arg_logits = model(encoded["input_ids"], encoded["attention_mask"])
            predicted_ops = op_logits.argmax(dim=-1)
            predicted_args = arg_logits.argmax(dim=-1)
            for row, example in enumerate(group):
                pred_op = int(predicted_ops[row])
                pred_args = tuple(int(x) for x in predicted_args[row].tolist())
                op_ok = pred_op == example.operation
                args_ok = pred_args == example.args
                is_exact = op_ok and args_ok
                op_correct += int(op_ok)
                arg_correct += sum(int(a == b) for a, b in zip(pred_args, example.args))
                arg_total += 4
                exact += int(is_exact)
                family_exact[example.family]["exact"] += int(is_exact)
                family_exact[example.family]["total"] += 1
                if not is_exact and len(mistakes) < 20:
                    mistakes.append(
                        {
                            "text": example.text,
                            "family": example.family,
                            "gold_operation": OPERATION_NAMES[example.operation],
                            "predicted_operation": OPERATION_NAMES[pred_op],
                            "gold_args": list(example.args),
                            "predicted_args": list(pred_args),
                            "slots": list(example.slots),
                        }
                    )

    report = {
        "model": args.model,
        "mode": "structured_operation_plus_pointers",
        "train_samples": len(train),
        "eval_samples": len(evaluation),
        "epochs": args.epochs,
        "total_parameters": total_parameters,
        "trainable_parameters": trainable_parameters,
        "operation_accuracy": op_correct / len(evaluation),
        "argument_accuracy": arg_correct / arg_total,
        "exact_structure": exact,
        "exact_structure_accuracy": exact / len(evaluation),
        "family_exact": dict(family_exact),
        "loss_history": loss_history,
        "mistakes": mistakes,
        "contract": {
            "operation_classes": list(OPERATION_NAMES),
            "max_slots": MAX_SLOTS,
            "none_slot": NONE_SLOT,
            "free_form_generation": False,
        },
    }
    Path("compiler-structured-results.json").write_text(json.dumps(report, indent=2))
    Path("semvm-structured-compiler-adapter").mkdir(exist_ok=True)
    model.backbone.save_pretrained("semvm-structured-compiler-adapter")
    torch.save(
        {
            "operation_head": model.operation_head.state_dict(),
            "argument_head": model.argument_head.state_dict(),
            "hidden_size": hidden,
        },
        "semvm-structured-compiler-adapter/structured_heads.pt",
    )

    print(f"model={args.model} total_parameters={total_parameters} trainable_parameters={trainable_parameters}")
    print(json.dumps({k: report[k] for k in (
        "mode", "train_samples", "eval_samples", "epochs", "trainable_parameters",
        "operation_accuracy", "argument_accuracy", "exact_structure", "exact_structure_accuracy",
        "family_exact", "loss_history"
    )}, indent=2))


if __name__ == "__main__":
    main()

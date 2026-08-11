from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random

import torch
from peft import LoraConfig, get_peft_model
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer

from compiler_corpus import SYSTEM_PROMPT, CompilerExample, generate_examples
from semzip.vm_bridge import VMProposalError, program_from_json

MODEL_ID = "HuggingFaceTB/SmolLM2-135M-Instruct"


class TokenDataset(Dataset):
    def __init__(self, tokenizer, examples: tuple[CompilerExample, ...], max_length: int):
        self.rows = [encode_example(tokenizer, x, max_length) for x in examples]

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        return self.rows[index]


def encode_example(tokenizer, example: CompilerExample, max_length: int):
    prompt_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": example.text},
    ]
    full_messages = prompt_messages + [{"role": "assistant", "content": example.target}]
    prompt_text = tokenizer.apply_chat_template(
        prompt_messages, tokenize=False, add_generation_prompt=True
    )
    full_text = tokenizer.apply_chat_template(
        full_messages, tokenize=False, add_generation_prompt=False
    )
    prompt_ids = tokenizer(
        prompt_text,
        add_special_tokens=False,
        truncation=True,
        max_length=max_length,
    )["input_ids"]
    full_ids = tokenizer(
        full_text,
        add_special_tokens=False,
        truncation=True,
        max_length=max_length,
    )["input_ids"]
    if len(full_ids) <= len(prompt_ids):
        raise ValueError("training target was truncated away; increase max_length")
    labels = [-100] * min(len(prompt_ids), len(full_ids)) + full_ids[len(prompt_ids):]
    return {
        "input_ids": full_ids,
        "labels": labels,
    }


def make_collate(tokenizer):
    pad = tokenizer.pad_token_id

    def collate(rows):
        width = max(len(x["input_ids"]) for x in rows)
        input_ids = []
        attention = []
        labels = []
        for row in rows:
            n = width - len(row["input_ids"])
            input_ids.append(row["input_ids"] + [pad] * n)
            attention.append([1] * len(row["input_ids"]) + [0] * n)
            labels.append(row["labels"] + [-100] * n)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }

    return collate


def extract_json(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return json.dumps(obj, separators=(",", ":"))


def signature(program):
    return tuple((ins.opcode, ins.args) for ins in program.instructions)


def evaluate(model, tokenizer, examples: tuple[CompilerExample, ...]):
    model.eval()
    rows = []
    family_exact = Counter()
    family_total = Counter()
    for example in examples:
        family_total[example.family] += 1
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": example.text},
        ]
        rendered = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(rendered, return_tensors="pt")
        with torch.inference_mode():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=220,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated = tokenizer.decode(
            generated_ids[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        ).strip()
        valid_json = valid_program = exact = False
        error = None
        try:
            payload = extract_json(generated)
            valid_json = True
            proposed = program_from_json(payload)
            valid_program = True
            gold = program_from_json(example.target)
            exact = signature(proposed) == signature(gold)
        except (ValueError, VMProposalError, json.JSONDecodeError) as exc:
            error = str(exc)
        if exact:
            family_exact[example.family] += 1
        rows.append(
            {
                "family": example.family,
                "text": example.text,
                "valid_json": valid_json,
                "valid_program": valid_program,
                "exact_program": exact,
                "generated": generated,
                "target": example.target,
                "error": error,
            }
        )
    return {
        "cases": len(rows),
        "valid_json": sum(x["valid_json"] for x in rows),
        "valid_program": sum(x["valid_program"] for x in rows),
        "exact_program": sum(x["exact_program"] for x in rows),
        "family_exact": {
            family: {"exact": family_exact[family], "total": family_total[family]}
            for family in sorted(family_total)
        },
        "results": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-samples", type=int, default=128)
    parser.add_argument("--eval-samples", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--max-length", type=int, default=384)
    parser.add_argument("--learning-rate", type=float, default=8e-4)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(min(4, max(1, torch.get_num_threads())))

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID)
    model.config.use_cache = False

    leaves = {name.rsplit(".", 1)[-1] for name, _ in model.named_modules()}
    targets = [name for name in ("q_proj", "v_proj") if name in leaves]
    if not targets:
        raise RuntimeError(f"could not find LoRA projection modules; sample leaves={sorted(leaves)[:50]}")
    lora = LoraConfig(
        r=4,
        lora_alpha=8,
        lora_dropout=0.0,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=targets,
    )
    model = get_peft_model(model, lora)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"model={MODEL_ID} total_parameters={total} trainable_parameters={trainable} targets={targets}")

    train_examples = generate_examples(args.train_samples, split="train", seed=args.seed)
    eval_examples = generate_examples(args.eval_samples, split="eval", seed=args.seed + 1)
    dataset = TokenDataset(tokenizer, train_examples, args.max_length)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=make_collate(tokenizer),
    )

    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad),
        lr=args.learning_rate,
    )
    model.train()
    loss_history = []
    for epoch in range(args.epochs):
        running = 0.0
        count = 0
        for batch in loader:
            optimizer.zero_grad(set_to_none=True)
            output = model(**batch)
            loss = output.loss
            if not torch.isfinite(loss):
                raise RuntimeError(f"non-finite loss: {loss.item()}")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                [p for p in model.parameters() if p.requires_grad], 1.0
            )
            optimizer.step()
            running += float(loss.item())
            count += 1
        avg = running / max(1, count)
        loss_history.append(avg)
        print(f"epoch={epoch + 1} average_loss={avg:.6f}")

    report = evaluate(model, tokenizer, eval_examples)
    report.update(
        {
            "model": MODEL_ID,
            "train_samples": args.train_samples,
            "eval_samples": args.eval_samples,
            "epochs": args.epochs,
            "trainable_parameters": trainable,
            "total_parameters": total,
            "loss_history": loss_history,
        }
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "model",
                    "train_samples",
                    "eval_samples",
                    "epochs",
                    "trainable_parameters",
                    "loss_history",
                    "valid_json",
                    "valid_program",
                    "exact_program",
                    "family_exact",
                )
            },
            indent=2,
        )
    )
    Path("compiler-finetune-results.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    out_dir = Path("semvm-compiler-adapter")
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)


if __name__ == "__main__":
    main()

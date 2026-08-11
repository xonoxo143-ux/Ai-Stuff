from __future__ import annotations

import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from semzip.vm_bridge import VMProposalError, program_from_json
from semzip.vm_compile import give, lend, move, sell

MODEL_ID = "HuggingFaceTB/SmolLM2-135M-Instruct"

ISA = """You are a compiler from short English statements into SemVM JSON.
Return ONLY one JSON object with this form:
{"instructions":[{"opcode":"K2","args":["subject","relation","value"]}]}

SemVM instructions:
K0(subject, relation, value) = set a value.
K1(subject, relation, before, after) = change an existing value.
K2(subject, relation, value) = require a value before acting.
K3(subject, relation) = clear a value.

Semantic rules:
- Giving transfers BOTH owner and possessor from giver to recipient.
- Receiving something from somebody is the same world transition as that person giving it.
- Lending keeps ownership with the lender, transfers possession to the borrower, and creates
  obligation:return:<item>:<borrower>:<lender> with status active.
- Selling transfers owner and possessor of the goods seller->buyer AND owner and possessor
  of the payment buyer->seller.
- Moving an object changes only its location.
- Use lowercase atoms. Do not invent facts that are not required by these rules.

Examples:
English: Alice gave Bob the key.
JSON: {"instructions":[{"opcode":"K2","args":["key","owner","alice"]},{"opcode":"K2","args":["key","possessor","alice"]},{"opcode":"K1","args":["key","owner","alice","bob"]},{"opcode":"K1","args":["key","possessor","alice","bob"]}]}

English: Nora moved the cup from shelf to table.
JSON: {"instructions":[{"opcode":"K2","args":["cup","location","shelf"]},{"opcode":"K1","args":["cup","location","shelf","table"]}]}

English: Eve lent Dan the bike.
JSON: {"instructions":[{"opcode":"K2","args":["bike","owner","eve"]},{"opcode":"K2","args":["bike","possessor","eve"]},{"opcode":"K1","args":["bike","possessor","eve","dan"]},{"opcode":"K0","args":["obligation:return:bike:dan:eve","status","active"]}]}
"""


def signature(program):
    return tuple((ins.opcode, ins.args) for ins in program.instructions)


def extract_json(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text[start:])
    return json.dumps(obj, separators=(",", ":"))


def main() -> None:
    torch.set_num_threads(2)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID)
    model.eval()

    cases = [
        ("John gave Mary the book.", give("john", "mary", "book")),
        ("Mary received the book from John.", give("john", "mary", "book")),
        ("John lent Mary the book.", lend("john", "mary", "book")),
        ("Mary moved the book from kitchen to garage.", move("mary", "book", "kitchen", "garage")),
        ("John sold Mary the book for the coin.", sell("john", "mary", "book", "coin")),
    ]

    rows = []
    for text, expected in cases:
        prompt = ISA + "\nEnglish: " + text + "\nJSON:"
        rendered = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(rendered, return_tensors="pt")
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=240,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated = tokenizer.decode(
            output[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        ).strip()

        valid_json = False
        valid_program = False
        exact = False
        parsed = None
        error = None
        try:
            payload = extract_json(generated)
            valid_json = True
            parsed = program_from_json(payload)
            valid_program = True
            exact = signature(parsed) == signature(expected)
        except (ValueError, VMProposalError, json.JSONDecodeError) as exc:
            error = str(exc)

        rows.append(
            {
                "text": text,
                "valid_json": valid_json,
                "valid_program": valid_program,
                "exact_program": exact,
                "generated": generated,
                "error": error,
            }
        )
        print(f"{text} json={valid_json} program={valid_program} exact={exact}")

    summary = {
        "model": MODEL_ID,
        "cases": len(rows),
        "valid_json": sum(r["valid_json"] for r in rows),
        "valid_program": sum(r["valid_program"] for r in rows),
        "exact_program": sum(r["exact_program"] for r in rows),
        "results": rows,
    }
    out = Path("compiler-probe-results.json")
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("model", "cases", "valid_json", "valid_program", "exact_program")}, indent=2))


if __name__ == "__main__":
    main()

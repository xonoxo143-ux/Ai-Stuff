from __future__ import annotations

import json
from typing import Any

from .vm_kernel import Instruction, Program


class VMProposalError(ValueError):
    pass


def program_from_data(data: Any) -> Program:
    """Validate an untrusted external compiler proposal into a VM Program."""
    if not isinstance(data, dict):
        raise VMProposalError("proposal must be an object")
    raw = data.get("instructions")
    if not isinstance(raw, list) or not raw:
        raise VMProposalError("instructions must be a non-empty list")
    instructions = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise VMProposalError(f"instruction {index} must be an object")
        opcode = item.get("opcode")
        args = item.get("args")
        if not isinstance(opcode, str):
            raise VMProposalError(f"instruction {index} opcode must be text")
        if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
            raise VMProposalError(f"instruction {index} args must be a list of strings")
        try:
            instructions.append(Instruction.make(opcode, *args))
        except ValueError as exc:
            raise VMProposalError(str(exc)) from exc
    label = data.get("label")
    if label is not None and not isinstance(label, str):
        raise VMProposalError("label must be text when present")
    return Program.build(instructions, label=label)


def program_from_json(payload: str) -> Program:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise VMProposalError("proposal is not valid JSON") from exc
    return program_from_data(data)

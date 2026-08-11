from __future__ import annotations

from .vm_kernel import Instruction, Program, K_CLEAR, K_REQUIRE, K_SET, K_SHIFT


def seed_object(item: str, owner: str, *, possessor: str | None = None, location: str | None = None) -> Program:
    possessor = possessor or owner
    instructions = [
        Instruction.make(K_SET, item, "owner", owner),
        Instruction.make(K_SET, item, "possessor", possessor),
    ]
    if location is not None:
        instructions.append(Instruction.make(K_SET, item, "location", location))
    return Program.build(instructions, label="seed_object")


def give(giver: str, recipient: str, item: str) -> Program:
    return Program.build(
        [
            Instruction.make(K_REQUIRE, item, "owner", giver),
            Instruction.make(K_REQUIRE, item, "possessor", giver),
            Instruction.make(K_SHIFT, item, "owner", giver, recipient),
            Instruction.make(K_SHIFT, item, "possessor", giver, recipient),
        ],
        label="give",
    )


def lend(lender: str, borrower: str, item: str) -> Program:
    obligation = f"obligation:return:{item}:{borrower}:{lender}"
    return Program.build(
        [
            Instruction.make(K_REQUIRE, item, "owner", lender),
            Instruction.make(K_REQUIRE, item, "possessor", lender),
            Instruction.make(K_SHIFT, item, "possessor", lender, borrower),
            Instruction.make(K_SET, obligation, "status", "active"),
        ],
        label="lend",
    )


def return_loan(lender: str, borrower: str, item: str) -> Program:
    obligation = f"obligation:return:{item}:{borrower}:{lender}"
    return Program.build(
        [
            Instruction.make(K_REQUIRE, item, "owner", lender),
            Instruction.make(K_SHIFT, item, "possessor", borrower, lender),
            Instruction.make(K_CLEAR, obligation, "status"),
        ],
        label="return_loan",
    )


def sell(seller: str, buyer: str, goods: str, payment: str) -> Program:
    return Program.build(
        [
            Instruction.make(K_REQUIRE, goods, "owner", seller),
            Instruction.make(K_REQUIRE, goods, "possessor", seller),
            Instruction.make(K_REQUIRE, payment, "owner", buyer),
            Instruction.make(K_REQUIRE, payment, "possessor", buyer),
            Instruction.make(K_SHIFT, goods, "owner", seller, buyer),
            Instruction.make(K_SHIFT, goods, "possessor", seller, buyer),
            Instruction.make(K_SHIFT, payment, "owner", buyer, seller),
            Instruction.make(K_SHIFT, payment, "possessor", buyer, seller),
        ],
        label="sell",
    )


def move(actor: str, subject: str, source: str, destination: str) -> Program:
    return Program.build(
        [
            Instruction.make(K_REQUIRE, subject, "location", source),
            Instruction.make(K_SHIFT, subject, "location", source, destination),
        ],
        label="move",
    )

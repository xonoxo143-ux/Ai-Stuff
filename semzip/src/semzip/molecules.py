from __future__ import annotations

from .meaning import Meaning


def change(
    subject: str,
    dimension: str,
    *,
    before: str | None = None,
    after: str,
    actor: str | None = None,
) -> Meaning:
    roles: dict[str, str] = {
        "subject": subject,
        "dimension": dimension,
        "after": after,
    }
    if before is not None:
        roles["before"] = before
    if actor is not None:
        roles["actor"] = actor
    return Meaning.build("CHANGE", roles)


def transfer_possession(item: str, source: str, destination: str) -> Meaning:
    """Canonical possession transfer independent of linguistic viewpoint."""
    return change(
        item,
        "owner",
        before=source,
        after=destination,
        actor=source,
    )


def give(giver: str, recipient: str, item: str) -> Meaning:
    return transfer_possession(item, giver, recipient)


def receive(recipient: str, item: str, source: str) -> Meaning:
    return transfer_possession(item, source, recipient)


def exchange(*, goods: str, seller: str, buyer: str, payment: str) -> Meaning:
    """Two reciprocal possession changes under one agreement."""
    return Meaning.build(
        "EXCHANGE",
        {
            "goods_transfer": transfer_possession(goods, seller, buyer),
            "payment_transfer": transfer_possession(payment, buyer, seller),
        },
    )


def sell(seller: str, buyer: str, goods: str, payment: str) -> Meaning:
    return exchange(goods=goods, seller=seller, buyer=buyer, payment=payment)


def buy(buyer: str, goods: str, seller: str, payment: str) -> Meaning:
    return exchange(goods=goods, seller=seller, buyer=buyer, payment=payment)


def loan(item: str, lender: str, borrower: str) -> Meaning:
    """Temporary possession transfer plus an explicit return expectation."""
    initial_transfer = transfer_possession(item, lender, borrower)
    return_obligation = Meaning.build(
        "OBLIGATION",
        {
            "holder": borrower,
            "content": transfer_possession(item, borrower, lender),
        },
    )
    return Meaning.build(
        "LOAN",
        {
            "transfer": initial_transfer,
            "return_obligation": return_obligation,
        },
    )


def lend(lender: str, borrower: str, item: str) -> Meaning:
    return loan(item, lender, borrower)


def borrow(borrower: str, item: str, lender: str) -> Meaning:
    return loan(item, lender, borrower)


def move(subject: str, source: str, destination: str) -> Meaning:
    return change(
        subject,
        "location",
        before=source,
        after=destination,
        actor=subject,
    )


def enter(subject: str, destination: str, *, source: str = "outside") -> Meaning:
    return move(subject, source, destination)


def leave(subject: str, source: str, *, destination: str = "outside") -> Meaning:
    return move(subject, source, destination)


def temperature_change(subject: str, before: str, after: str) -> Meaning:
    return change(subject, "temperature", before=before, after=after)


def size_change(subject: str, before: str, after: str) -> Meaning:
    return change(subject, "size", before=before, after=after)

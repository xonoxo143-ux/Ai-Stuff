from __future__ import annotations

from .meaning import Meaning


_QUANTIFIERS = {"ALL", "SOME", "NONE", "EXACT", "MOST"}


def set_of_type(type_name: str) -> Meaning:
    return Meaning.build("SET_OF_TYPE", {"type": type_name})


def quantify(
    type_name: str,
    quantifier: str,
    *,
    count: int | None = None,
) -> Meaning:
    q = quantifier.strip().upper()
    if q not in _QUANTIFIERS:
        raise ValueError(f"unsupported quantifier {quantifier!r}")
    if q == "EXACT":
        if count is None or count < 0:
            raise ValueError("EXACT quantifier requires a non-negative count")
    elif count is not None:
        raise ValueError(f"{q} quantifier does not take an exact count")

    roles: dict[str, object] = {
        "quantifier": q,
        "domain": set_of_type(type_name),
    }
    if count is not None:
        roles["count"] = count
    return Meaning.build("QUANTIFIED_SET", roles)

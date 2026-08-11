from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .meaning import Meaning


class SemanticType(str, Enum):
    ATOM = "atom"
    EXPRESSION = "expression"
    EXPRESSIONS = "expressions"
    ATOMS = "atoms"
    SCALAR = "scalar"


@dataclass(frozen=True, slots=True)
class OperatorSpec:
    required: Mapping[str, SemanticType]
    optional: Mapping[str, SemanticType] | None = None

    def __post_init__(self) -> None:
        if self.optional is None:
            object.__setattr__(self, "optional", {})


class SemanticValidationError(ValueError):
    pass


ATOM = SemanticType.ATOM
EXPR = SemanticType.EXPRESSION
EXPRS = SemanticType.EXPRESSIONS
ATOMS = SemanticType.ATOMS
SCALAR = SemanticType.SCALAR

SPECS: dict[str, OperatorSpec] = {
    "STATE": OperatorSpec({"SUBJECT": ATOM, "DIMENSION": ATOM, "VALUE": ATOM}),
    "CHANGE": OperatorSpec(
        {"SUBJECT": ATOM, "DIMENSION": ATOM, "AFTER": ATOM},
        {"BEFORE": ATOM, "ACTOR": ATOM},
    ),
    "BELIEVE": OperatorSpec({"HOLDER": ATOM, "CONTENT": EXPR}),
    "KNOW_VALUE": OperatorSpec(
        {"HOLDER": ATOM, "SUBJECT": ATOM, "DIMENSION": ATOM},
        {"VALUE": ATOM},
    ),
    "NOT": OperatorSpec({"CONTENT": EXPR}),
    "IS_A": OperatorSpec({"CHILD": ATOM, "PARENT": ATOM}),
    "POSSIBLE": OperatorSpec({"CONTENT": EXPR}),
    "PROBABLE": OperatorSpec({"CONTENT": EXPR}),
    "NECESSARY": OperatorSpec({"CONTENT": EXPR}),
    "INTENDED": OperatorSpec({"CONTENT": EXPR}, {"HOLDER": ATOM}),
    "ATTEMPTED": OperatorSpec({"CONTENT": EXPR}, {"ACTOR": ATOM}),
    "COUNTERFACTUAL": OperatorSpec({"CONTENT": EXPR}),
    "CONDITIONAL": OperatorSpec({"IF": EXPR, "THEN": EXPR}),
    "CAUSE": OperatorSpec({"CAUSE": EXPR, "EFFECT": EXPR}),
    "ENABLE": OperatorSpec({"CAUSE": EXPR, "EFFECT": EXPR}),
    "PREVENT": OperatorSpec({"CAUSE": EXPR, "EFFECT": EXPR}),
    "CORRELATE": OperatorSpec({"LEFT": EXPR, "RIGHT": EXPR}),
    "PRECEDE": OperatorSpec({"BEFORE": EXPR, "AFTER": EXPR}),
    "EVENT": OperatorSpec({"NAME": ATOM}),
    "EXCHANGE": OperatorSpec({"GOODS_TRANSFER": EXPR, "PAYMENT_TRANSFER": EXPR}),
    "OBLIGATION": OperatorSpec({"HOLDER": ATOM, "CONTENT": EXPR}),
    "LOAN": OperatorSpec({"TRANSFER": EXPR, "RETURN_OBLIGATION": EXPR}),
    "QUERY_VALUE": OperatorSpec({"SUBJECT": ATOM, "DIMENSION": ATOM}),
    "QUERY_PREVIOUS_VALUE": OperatorSpec({"SUBJECT": ATOM, "DIMENSION": ATOM}),
    "QUERY_BELIEF": OperatorSpec(
        {"HOLDER": ATOM, "SUBJECT": ATOM, "DIMENSION": ATOM}
    ),
    "QUERY_BELIEF_TRUE": OperatorSpec(
        {"HOLDER": ATOM, "SUBJECT": ATOM, "DIMENSION": ATOM}
    ),
    "QUERY_KNOWS_VALUE": OperatorSpec(
        {"HOLDER": ATOM, "SUBJECT": ATOM, "DIMENSION": ATOM}
    ),
    "QUERY_IS_A": OperatorSpec({"SUBJECT": ATOM, "ANCESTOR": ATOM}),
    "AMBIGUITY": OperatorSpec({"OPTIONS": EXPRS}),
    "BUNDLE": OperatorSpec({"ITEMS": EXPRS}),
    "SET": OperatorSpec({"MEMBERS": ATOMS}),
    "SET_OF_TYPE": OperatorSpec({"TYPE": ATOM}),
    "QUANTIFIED_SET": OperatorSpec(
        {"QUANTIFIER": ATOM, "DOMAIN": EXPR},
        {"COUNT": SCALAR},
    ),
    "QUERY_MEMBERS_OF_TYPE": OperatorSpec({"TYPE": ATOM}),
    "QUERY_COUNT_TYPE": OperatorSpec({"TYPE": ATOM}),
}


def validate_meaning(meaning: Meaning, *, recursive: bool = True) -> None:
    spec = SPECS.get(meaning.operator)
    if spec is None:
        raise SemanticValidationError(f"unknown semantic operator {meaning.operator!r}")

    values = dict(meaning.roles)
    required = set(spec.required)
    optional = set(spec.optional)
    missing = required - set(values)
    extra = set(values) - required - optional

    if missing:
        raise SemanticValidationError(
            f"{meaning.operator} missing required roles: {sorted(missing)}"
        )
    if extra:
        raise SemanticValidationError(
            f"{meaning.operator} has unknown roles: {sorted(extra)}"
        )

    for role, expected in {**spec.required, **spec.optional}.items():
        if role not in values:
            continue
        value = values[role]
        _validate_value(meaning.operator, role, value, expected)
        if recursive and isinstance(value, Meaning):
            validate_meaning(value, recursive=True)
        elif recursive and isinstance(value, tuple):
            for item in value:
                if isinstance(item, Meaning):
                    validate_meaning(item, recursive=True)


def _validate_value(
    operator: str,
    role: str,
    value: object,
    expected: SemanticType,
) -> None:
    if expected is SemanticType.EXPRESSION:
        ok = isinstance(value, Meaning)
    elif expected is SemanticType.EXPRESSIONS:
        ok = isinstance(value, tuple) and all(
            isinstance(item, Meaning) for item in value
        )
    elif expected is SemanticType.ATOMS:
        ok = isinstance(value, tuple) and all(
            isinstance(item, str) for item in value
        )
    elif expected is SemanticType.ATOM:
        ok = isinstance(value, str)
    else:
        ok = isinstance(value, (str, bool, int, float))

    if not ok:
        raise SemanticValidationError(
            f"{operator}.{role} expected {expected.value}, "
            f"got {type(value).__name__}"
        )

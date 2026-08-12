from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable, Mapping, Sequence

from .vm_effects import ShiftEffect
from .vm_patch import SemanticPatch
from .vm_state import StateSnapshot
from .vm_transform import SemanticTransform, StateConstraint


Bindings = Mapping[str, str]
TransformBuilder = Callable[[Bindings], SemanticTransform]
BindingPredicate = Callable[[Bindings, StateSnapshot], bool]


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    domain: str


@dataclass(frozen=True, slots=True)
class ActionSchema:
    """Generic parameterized semantic transform available to a planner.

    `name` is debug/library metadata, not a semantic opcode. The planner only sees
    parameters, candidate domains, and the resulting SemanticTransform.
    """

    name: str
    parameters: tuple[Parameter, ...]
    build_transform: TransformBuilder
    binding_predicate: BindingPredicate | None = None

    def groundings(
        self,
        snapshot: StateSnapshot,
        domains: Mapping[str, Sequence[str]],
    ) -> tuple[tuple[dict[str, str], SemanticTransform], ...]:
        values: list[Sequence[str]] = []
        for parameter in self.parameters:
            domain_values = domains.get(parameter.domain)
            if domain_values is None:
                raise KeyError(
                    f"schema {self.name!r} requires missing domain {parameter.domain!r}"
                )
            values.append(domain_values)

        grounded = []
        for choice in product(*values):
            bindings = {
                parameter.name: str(value)
                for parameter, value in zip(self.parameters, choice)
            }
            if self.binding_predicate is not None and not self.binding_predicate(bindings, snapshot):
                continue
            grounded.append((bindings, self.build_transform(bindings)))
        return tuple(grounded)


def toy_transfer_schema() -> ActionSchema:
    """Compatibility schema for the early ownership+possession planning world."""

    def build(b: Bindings) -> SemanticTransform:
        return SemanticTransform.build(
            SemanticPatch.build(effects=(
                ShiftEffect.build(b["object"], "owner", b["source"], b["destination"]),
                ShiftEffect.build(b["object"], "possessor", b["source"], b["destination"]),
            ))
        )

    return ActionSchema(
        "transfer_owner_and_possession",
        (
            Parameter("object", "objects"),
            Parameter("source", "agents"),
            Parameter("destination", "agents"),
        ),
        build,
        lambda b, _state: b["source"] != b["destination"],
    )


def toy_location_schema(
    neighbors: Mapping[str, Sequence[str]],
) -> ActionSchema:
    """Compatibility schema for location movement in the synthetic planning world."""

    normalized = {str(key): tuple(str(value) for value in values) for key, values in neighbors.items()}

    def build(b: Bindings) -> SemanticTransform:
        return SemanticTransform.build(
            SemanticPatch.build(effects=(
                ShiftEffect.build(b["object"], "location", b["source"], b["destination"]),
            )),
            constraints=(
                StateConstraint.build(b["object"], "possessor", b["holder"]),
            ),
        )

    return ActionSchema(
        "shift_location",
        (
            Parameter("object", "objects"),
            Parameter("holder", "agents"),
            Parameter("source", "rooms"),
            Parameter("destination", "rooms"),
        ),
        build,
        lambda b, _state: b["destination"] in normalized.get(b["source"], ()),
    )

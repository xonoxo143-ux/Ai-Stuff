from __future__ import annotations

from dataclasses import dataclass

from .vm_kernel import Program
from .vm_ledger import atom


SUPPORTED_RELATIONS = ("owner", "possessor", "location")


@dataclass(frozen=True, slots=True)
class RelationDelta:
    """One entity changing one or more grounded world relations."""

    subject: str
    source: str
    destination: str
    relations: tuple[str, ...]

    @classmethod
    def build(
        cls,
        subject: str,
        source: str,
        destination: str,
        relations: tuple[str, ...] | list[str],
    ) -> "RelationDelta":
        normalized = tuple(atom(x) for x in relations)
        if not normalized:
            raise ValueError("relation delta must change at least one relation")
        if len(set(normalized)) != len(normalized):
            raise ValueError("relation delta contains duplicate relations")
        unknown = tuple(x for x in normalized if x not in SUPPORTED_RELATIONS)
        if unknown:
            raise ValueError(f"unsupported grounded relations: {unknown}")
        ordered = tuple(sorted(normalized, key=SUPPORTED_RELATIONS.index))
        return cls(atom(subject), atom(source), atom(destination), ordered)

    def transition_key(self) -> tuple[str, str, str, tuple[str, ...]]:
        return (self.subject, self.source, self.destination, self.relations)


@dataclass(frozen=True, slots=True)
class SemanticDeltaFrame:
    """Compatibility frame for the earlier one/two-delta compiler boundary.

    New code should prefer SemanticPatch, which supports any number of unordered
    relation deltas. This type remains useful for existing benchmarks/adapters.
    """

    primary: RelationDelta
    secondary: RelationDelta | None = None
    return_obligation: bool = False

    def to_patch(self):
        from .vm_patch import ReturnObligation, SemanticPatch

        deltas = (self.primary,) if self.secondary is None else (self.primary, self.secondary)
        obligations = ()
        if self.return_obligation:
            if "possessor" not in self.primary.relations:
                raise ValueError("return obligation requires a primary possession transition")
            obligations = (
                ReturnObligation.build(
                    self.primary.subject,
                    self.primary.destination,
                    self.primary.source,
                ),
            )
        return SemanticPatch.build(deltas, return_obligations=obligations)

    def transition_fingerprint(self) -> tuple:
        return self.to_patch().transition_fingerprint()

    def transition_equivalent(self, other: "SemanticDeltaFrame") -> bool:
        return self.transition_fingerprint() == other.transition_fingerprint()


def compile_delta_frame(frame: SemanticDeltaFrame) -> Program:
    from .vm_patch import compile_semantic_patch

    return compile_semantic_patch(frame.to_patch())

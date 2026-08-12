from __future__ import annotations

from dataclasses import dataclass

from .vm_patch_bridge import PatchPrediction, RelationCellPrediction


@dataclass(frozen=True, slots=True)
class RelationEvidence:
    relation_id: int
    subject: int
    source: int
    destination: int
    confidence: float

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")

    def cell_key(self) -> tuple[int, int]:
        return (self.relation_id, self.subject)

    def effect_key(self) -> tuple[int, int]:
        return (self.source, self.destination)


@dataclass(frozen=True, slots=True)
class AmbiguousRelationEvidence:
    relation_id: int
    subject: int
    candidates: tuple[RelationEvidence, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class EvidenceResolution:
    relation_registry_signature: str
    accepted: tuple[RelationEvidence, ...]
    ambiguous: tuple[AmbiguousRelationEvidence, ...]
    low_confidence: tuple[RelationEvidence, ...]

    @property
    def executable(self) -> bool:
        return bool(self.accepted) and not self.ambiguous

    def patch_prediction(self) -> PatchPrediction | None:
        if not self.accepted:
            return None
        if self.ambiguous:
            return None
        return PatchPrediction(
            self.relation_registry_signature,
            tuple(
                RelationCellPrediction(
                    item.relation_id,
                    item.subject,
                    item.source,
                    item.destination,
                )
                for item in self.accepted
            ),
        )


def resolve_relation_evidence(
    relation_registry_signature: str,
    evidence,
    *,
    min_confidence: float = 0.80,
    min_margin: float = 0.10,
) -> EvidenceResolution:
    """Resolve neural relation candidates without converting uncertainty to truth.

    Candidates compete only within the same `(relation_id, subject)` semantic cell.
    Identical effects collapse to their strongest confidence. A top candidate must
    clear both an absolute confidence threshold and a margin over the runner-up.
    Otherwise the cell remains explicit ambiguity and produces no executable patch.
    """

    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be in [0, 1]")
    if not 0.0 <= min_margin <= 1.0:
        raise ValueError("min_margin must be in [0, 1]")

    grouped: dict[tuple[int, int], dict[tuple[int, int], RelationEvidence]] = {}
    for item in evidence:
        if not isinstance(item, RelationEvidence):
            raise TypeError("all evidence values must be RelationEvidence")
        effects = grouped.setdefault(item.cell_key(), {})
        previous = effects.get(item.effect_key())
        if previous is None or item.confidence > previous.confidence:
            effects[item.effect_key()] = item

    accepted: list[RelationEvidence] = []
    ambiguous: list[AmbiguousRelationEvidence] = []
    low_confidence: list[RelationEvidence] = []

    for (relation_id, subject), by_effect in sorted(grouped.items()):
        ranked = sorted(
            by_effect.values(),
            key=lambda item: (
                item.confidence,
                -item.source,
                -item.destination,
            ),
            reverse=True,
        )
        top = ranked[0]
        if top.confidence < min_confidence:
            low_confidence.extend(ranked)
            continue
        runner_up = ranked[1] if len(ranked) > 1 else None
        if runner_up is not None and top.confidence - runner_up.confidence < min_margin:
            ambiguous.append(
                AmbiguousRelationEvidence(
                    relation_id,
                    subject,
                    tuple(ranked),
                    "top candidates are too close",
                )
            )
            continue
        accepted.append(top)

    return EvidenceResolution(
        relation_registry_signature,
        tuple(accepted),
        tuple(ambiguous),
        tuple(low_confidence),
    )

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from .vm_delta import RelationDelta
from .vm_mentions import SlottedText, slotize_mentions
from .vm_patch import ReturnObligation, SemanticPatch, StateAssignment, StateClear
from .vm_semantic_parse import AtomicCompiler
from .vm_sequence import SemanticSequence
from .vm_sequence_parse import SemanticSequenceParse, parse_semantic_sequence


@dataclass(frozen=True, slots=True)
class MentionCandidate:
    start: int
    end: int
    confidence: float

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("mention confidence must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class FrontendResult:
    raw_text: str
    slotted: SlottedText
    parse: SemanticSequenceParse
    grounded_sequence: SemanticSequence


MentionDetector = Callable[[str], Sequence[MentionCandidate]]


def select_mentions(
    text: str,
    candidates: Sequence[MentionCandidate],
    *,
    min_confidence: float = 0.80,
) -> tuple[tuple[int, int], ...]:
    """Select non-overlapping high-confidence mention spans conservatively."""

    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be in [0, 1]")
    accepted = sorted(
        (item for item in candidates if item.confidence >= min_confidence),
        key=lambda item: (item.start, item.end),
    )
    spans: list[tuple[int, int]] = []
    previous_end = -1
    for item in accepted:
        if not 0 <= item.start < item.end <= len(text):
            raise ValueError(f"invalid mention span {(item.start, item.end)}")
        if item.start < previous_end:
            raise ValueError("high-confidence mention candidates overlap")
        spans.append((item.start, item.end))
        previous_end = item.end
    return tuple(spans)


def _slot_value(value: str, entities: tuple[str, ...]) -> str:
    # Semantic atoms are case-folded, so compiler-produced E2 becomes e2 after a
    # patch is built. Slot identity must therefore be syntax-aware, not case-aware.
    if len(value) >= 2 and value[0].casefold() == "e" and value[1:].isdigit():
        index = int(value[1:])
        if not 0 <= index < len(entities):
            raise ValueError(f"semantic patch references missing entity slot {value}")
        return entities[index]
    return value


def ground_patch_slots(patch: SemanticPatch, entities: Sequence[str]) -> SemanticPatch:
    table = tuple(str(value) for value in entities)
    deltas = tuple(
        RelationDelta.build(
            _slot_value(delta.subject, table),
            _slot_value(delta.source, table),
            _slot_value(delta.destination, table),
            delta.relations,
        )
        for delta in patch.deltas
    )
    assignments = tuple(
        StateAssignment.build(
            _slot_value(item.subject, table),
            item.dimension,
            _slot_value(item.value, table),
        )
        for item in patch.assignments
    )
    clears = tuple(
        StateClear.build(_slot_value(item.subject, table), item.dimension)
        for item in patch.clears
    )
    obligations = tuple(
        ReturnObligation.build(
            _slot_value(item.subject, table),
            _slot_value(item.holder, table),
            _slot_value(item.return_to, table),
        )
        for item in patch.return_obligations
    )
    return SemanticPatch.build(
        deltas,
        assignments=assignments,
        clears=clears,
        return_obligations=obligations,
    )


def ground_sequence_slots(
    sequence: SemanticSequence,
    entities: Sequence[str],
) -> SemanticSequence:
    return SemanticSequence.build(
        ground_patch_slots(step, entities) for step in sequence.steps
    )


def compile_raw_utterance(
    text: str,
    mention_detector: MentionDetector,
    atomic_compiler: AtomicCompiler,
    *,
    min_mention_confidence: float = 0.80,
    sequence_penalty: float = 0.04,
    split_penalty: float = 0.08,
    max_steps: int = 8,
    max_parts_per_step: int = 8,
    beam_width: int = 16,
) -> FrontendResult | None:
    candidates = tuple(mention_detector(text))
    spans = select_mentions(
        text,
        candidates,
        min_confidence=min_mention_confidence,
    )
    if not spans:
        return None
    slotted = slotize_mentions(text, spans)
    parsed = parse_semantic_sequence(
        slotted.text,
        atomic_compiler,
        sequence_penalty=sequence_penalty,
        split_penalty=split_penalty,
        max_steps=max_steps,
        max_parts_per_step=max_parts_per_step,
        beam_width=beam_width,
    )
    if parsed is None:
        return None
    grounded = ground_sequence_slots(parsed.sequence, slotted.entities)
    return FrontendResult(text, slotted, parsed, grounded)

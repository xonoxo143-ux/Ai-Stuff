from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from .vm_frontend import FrontendResult, MentionDetector, compile_raw_utterance, ground_sequence_slots
from .vm_mentions import SlottedText
from .vm_semantic_parse import AtomicCompiler
from .vm_sequence import SemanticSequence


EntityResolver = Callable[[SlottedText], Sequence[str]]


@dataclass(frozen=True, slots=True)
class ResolvedFrontendResult:
    raw: FrontendResult
    entity_ids: tuple[str, ...]
    grounded_sequence: SemanticSequence


def distinct_mention_ids(slotted: SlottedText) -> tuple[str, ...]:
    """Safe default: no coreference assumption whatsoever."""

    return tuple(f"mention#{index}" for index in range(len(slotted.entities)))


def compile_resolved_utterance(
    text: str,
    mention_detector: MentionDetector,
    atomic_compiler: AtomicCompiler,
    *,
    entity_resolver: EntityResolver = distinct_mention_ids,
    min_mention_confidence: float = 0.80,
    sequence_penalty: float = 0.04,
    split_penalty: float = 0.08,
    max_steps: int = 8,
    max_parts_per_step: int = 8,
    beam_width: int = 16,
) -> ResolvedFrontendResult | None:
    """Compile raw language while keeping surface mentions separate from identity.

    The underlying frontend's surface-grounded convenience result is intentionally
    ignored here. `entity_resolver` is the only authority allowed to map mention slots
    onto persistent world IDs. The default creates distinct IDs for every mention.
    """

    raw = compile_raw_utterance(
        text,
        mention_detector,
        atomic_compiler,
        min_mention_confidence=min_mention_confidence,
        sequence_penalty=sequence_penalty,
        split_penalty=split_penalty,
        max_steps=max_steps,
        max_parts_per_step=max_parts_per_step,
        beam_width=beam_width,
    )
    if raw is None:
        return None

    resolved = tuple(str(value) for value in entity_resolver(raw.slotted))
    if len(resolved) != len(raw.slotted.entities):
        raise ValueError(
            "entity resolver must return exactly one identity for each mention slot"
        )
    if any(not value for value in resolved):
        raise ValueError("entity resolver returned an empty identity")

    grounded = ground_sequence_slots(raw.parse.sequence, resolved)
    return ResolvedFrontendResult(raw, resolved, grounded)

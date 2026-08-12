from __future__ import annotations

from dataclasses import dataclass
import re

from .vm_semantic_parse import AtomicCompiler, SemanticParse, parse_semantics
from .vm_sequence import SemanticSequence


_SEQUENCE_PATTERNS = (
    re.compile(r"\s+(?:and\s+then|then|after\s+that|subsequently)\s+", re.I),
    re.compile(r"\s*;\s*(?:then|after\s+that)\s+", re.I),
)


@dataclass(frozen=True, slots=True)
class SemanticSequenceParse:
    sequence: SemanticSequence
    score: float
    segments: tuple[str, ...]
    step_parses: tuple[SemanticParse, ...]


def candidate_sequence_splits(text: str) -> tuple[tuple[str, str], ...]:
    normalized = " ".join(text.strip().split())
    seen = set()
    result = []
    for pattern in _SEQUENCE_PATTERNS:
        for match in pattern.finditer(normalized):
            left = normalized[: match.start()].strip(" ,;.")
            right = normalized[match.end() :].strip(" ,;.")
            if not left or not right:
                continue
            pair = (left, right)
            if pair not in seen:
                seen.add(pair)
                result.append(pair)
    return tuple(result)


def parse_semantic_sequence(
    text: str,
    atomic_compiler: AtomicCompiler,
    *,
    sequence_penalty: float = 0.04,
    split_penalty: float = 0.08,
    max_steps: int = 8,
    max_parts_per_step: int = 8,
    beam_width: int = 16,
) -> SemanticSequenceParse | None:
    """Parse explicit temporal markers as ordered state updates.

    Explicit sequence words are authoritative about ordering at this layer: if a span
    contains `then`/`after that`, the parser does not reinterpret that marker as a
    parallel patch union. Within each temporal step, the existing recursive semantic
    parser is still free to compose compatible conjunctions.
    """

    normalized = " ".join(text.strip().split())
    if not normalized:
        return None

    def solve(span: str) -> list[SemanticSequenceParse]:
        sequence_splits = candidate_sequence_splits(span)
        if not sequence_splits:
            parsed = parse_semantics(
                span,
                atomic_compiler,
                split_penalty=split_penalty,
                max_parts=max_parts_per_step,
                beam_width=beam_width,
            )
            if parsed is None:
                return []
            return [
                SemanticSequenceParse(
                    SemanticSequence.build((parsed.patch,)),
                    parsed.score,
                    (span,),
                    (parsed,),
                )
            ]

        candidates: list[SemanticSequenceParse] = []
        for left_text, right_text in sequence_splits:
            for left in solve(left_text):
                for right in solve(right_text):
                    steps = left.sequence.steps + right.sequence.steps
                    if len(steps) > max_steps:
                        continue
                    candidates.append(
                        SemanticSequenceParse(
                            SemanticSequence.build(steps),
                            left.score + right.score - sequence_penalty,
                            left.segments + right.segments,
                            left.step_parses + right.step_parses,
                        )
                    )
        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:beam_width]

    candidates = solve(normalized)
    return candidates[0] if candidates else None

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import re
from typing import Callable, Iterable, Sequence

from .vm_patch import SemanticPatch, compose_semantic_patches


@dataclass(frozen=True, slots=True)
class AtomicSemanticCandidate:
    patch: SemanticPatch
    confidence: float
    label: str = "atomic"

    def __post_init__(self):
        if not (0.0 < self.confidence <= 1.0):
            raise ValueError("candidate confidence must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class SemanticParse:
    patch: SemanticPatch
    score: float
    spans: tuple[str, ...]
    atomic_labels: tuple[str, ...]

    @property
    def parts(self) -> int:
        return len(self.spans)


AtomicCompiler = Callable[[str], Sequence[AtomicSemanticCandidate]]


# These are merely candidate boundaries, never authoritative syntax. A split is
# retained only if both sides can be compiled into compatible semantics.
_BOUNDARY_PATTERNS = (
    re.compile(r"(?<=[.!?;])\s+"),
    re.compile(r"\s+(?:and then|then|while|but|and|also)\s+", re.I),
    re.compile(r"\s*,\s*(?:and|while|but)\s+", re.I),
)


def candidate_splits(text: str) -> tuple[tuple[str, str], ...]:
    """Enumerate plausible binary splits without claiming any is grammatically right."""

    normalized = " ".join(text.strip().split())
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for pattern in _BOUNDARY_PATTERNS:
        for match in pattern.finditer(normalized):
            left = normalized[: match.start()].strip(" ,;.")
            right = normalized[match.end() :].strip(" ,;.")
            if not left or not right:
                continue
            pair = (left, right)
            if pair not in seen:
                seen.add(pair)
                out.append(pair)
    return tuple(out)


def parse_semantics(
    text: str,
    atomic_compiler: AtomicCompiler,
    *,
    split_penalty: float = 0.08,
    max_parts: int = 8,
    beam_width: int = 16,
) -> SemanticParse | None:
    """Recursively search for a valid composition of atomic semantic patches.

    Scores are sums of log-confidence with a small structural penalty for each
    composition boundary. The parser never overwrites conflicts: incompatible
    patches are discarded by compose_semantic_patches.
    """

    if max_parts < 1:
        raise ValueError("max_parts must be >= 1")
    if beam_width < 1:
        raise ValueError("beam_width must be >= 1")
    normalized = " ".join(text.strip().split())
    if not normalized:
        return None

    @lru_cache(maxsize=None)
    def solve(span: str) -> tuple[SemanticParse, ...]:
        parses: list[SemanticParse] = []

        for candidate in atomic_compiler(span):
            parses.append(
                SemanticParse(
                    patch=candidate.patch,
                    score=math.log(candidate.confidence),
                    spans=(span,),
                    atomic_labels=(candidate.label,),
                )
            )

        for left_text, right_text in candidate_splits(span):
            left_parses = solve(left_text)
            right_parses = solve(right_text)
            for left in left_parses:
                for right in right_parses:
                    if left.parts + right.parts > max_parts:
                        continue
                    try:
                        patch = compose_semantic_patches(left.patch, right.patch)
                    except ValueError:
                        continue
                    parses.append(
                        SemanticParse(
                            patch=patch,
                            score=left.score + right.score - split_penalty,
                            spans=left.spans + right.spans,
                            atomic_labels=left.atomic_labels + right.atomic_labels,
                        )
                    )

        # Deduplicate effect-equivalent parses, keeping the best-scoring derivation.
        best_by_effect: dict[tuple, SemanticParse] = {}
        for parse in parses:
            key = parse.patch.transition_fingerprint()
            previous = best_by_effect.get(key)
            if previous is None or parse.score > previous.score:
                best_by_effect[key] = parse
        ranked = sorted(best_by_effect.values(), key=lambda item: item.score, reverse=True)
        return tuple(ranked[:beam_width])

    results = solve(normalized)
    return results[0] if results else None

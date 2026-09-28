from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence


class CapabilityRole(str, Enum):
    CONTRIBUTOR = "contributor"
    COMPOSER = "composer"


@dataclass(frozen=True)
class PublicMessage:
    """Bounded public payload exchanged between capabilities."""

    kind: str
    content: Any
    source: str
    confidence: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityOffer:
    capability: str
    relevance: float
    estimated_cost: float = 0.0
    confidence: float = 1.0
    tags: tuple[str, ...] = ()

    @property
    def utility_hint(self) -> float:
        return self.relevance * self.confidence - self.estimated_cost


@dataclass(frozen=True)
class CapabilityContext:
    turn_id: int
    user_text: str
    active_state: Mapping[str, Any]
    recent_episodes: Sequence[Mapping[str, Any]]
    semantic_memory: Mapping[str, Any]
    contributions: Sequence[PublicMessage] = ()


@dataclass(frozen=True)
class CapabilityResult:
    messages: tuple[PublicMessage, ...] = ()
    active_state_updates: Mapping[str, Any] = field(default_factory=dict)
    semantic_updates: Mapping[str, Any] = field(default_factory=dict)
    measured_cost: float = 0.0
    success: bool = True
    error: str | None = None


class Capability(Protocol):
    name: str
    role: CapabilityRole
    contract_version: str

    def offer(self, context: CapabilityContext) -> CapabilityOffer | None:
        ...

    def run(self, context: CapabilityContext) -> CapabilityResult:
        ...

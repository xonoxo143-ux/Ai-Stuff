from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Iterable

from .contracts import (
    Capability,
    CapabilityContext,
    CapabilityOffer,
    CapabilityResult,
    CapabilityRole,
    PublicMessage,
)
from .memory import AgentMemory


@dataclass(frozen=True)
class RuntimeConfig:
    max_contributors: int = 4
    min_utility_hint: float = 0.0
    contributor_budget: float = 4.0


@dataclass
class ExecutionRecord:
    capability: str
    role: str
    offered_relevance: float | None
    offered_cost: float | None
    selected: bool
    success: bool | None = None
    measured_cost: float | None = None
    latency_ms: float | None = None
    error: str | None = None


@dataclass
class TurnTrace:
    turn_id: int
    user_text: str
    offers: list[dict] = field(default_factory=list)
    executions: list[ExecutionRecord] = field(default_factory=list)
    response: str = ""
    response_metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "user_text": self.user_text,
            "offers": self.offers,
            "executions": [asdict(x) for x in self.executions],
            "response": self.response,
            "response_metadata": dict(self.response_metadata),
        }


class AgentRuntime:
    """Minimal capability ecology shell with a swappable composer/language spine."""

    def __init__(
        self,
        *,
        composer: Capability,
        contributors: Iterable[Capability] = (),
        memory: AgentMemory | None = None,
        config: RuntimeConfig | None = None,
    ) -> None:
        if composer.role != CapabilityRole.COMPOSER:
            raise ValueError("composer must have role=COMPOSER")
        self.composer = composer
        self.contributors = list(contributors)
        self.memory = memory or AgentMemory()
        self.config = config or RuntimeConfig()
        self.turn_id = 0

    def _context(self, user_text: str, contributions=()) -> CapabilityContext:
        return CapabilityContext(
            turn_id=self.turn_id,
            user_text=user_text,
            active_state=dict(self.memory.active),
            recent_episodes=self.memory.recent_episodes(),
            semantic_memory=dict(self.memory.semantic),
            contributions=tuple(contributions),
        )

    def _select(
        self,
        context: CapabilityContext,
    ) -> tuple[list[Capability], dict[str, CapabilityOffer]]:
        offers: dict[str, CapabilityOffer] = {}
        candidates: list[tuple[float, str, Capability, CapabilityOffer]] = []
        for capability in self.contributors:
            offer = capability.offer(context)
            if offer is None:
                continue
            if offer.capability != capability.name:
                raise ValueError(f"offer name mismatch for {capability.name}")
            offers[capability.name] = offer
            if offer.utility_hint >= self.config.min_utility_hint:
                candidates.append(
                    (offer.utility_hint, capability.name, capability, offer)
                )

        candidates.sort(key=lambda row: (-row[0], row[1]))
        selected: list[Capability] = []
        budget = float(self.config.contributor_budget)
        for _utility, _name, capability, offer in candidates:
            if len(selected) >= self.config.max_contributors:
                break
            if offer.estimated_cost > budget:
                continue
            selected.append(capability)
            budget -= offer.estimated_cost
        return selected, offers

    def turn(self, user_text: str) -> tuple[str, TurnTrace]:
        self.turn_id += 1
        trace = TurnTrace(turn_id=self.turn_id, user_text=user_text)
        self.memory.append_episode(
            {"turn": self.turn_id, "role": "user", "text": user_text}
        )

        base_context = self._context(user_text)
        selected, offers = self._select(base_context)
        trace.offers = [asdict(offers[name]) for name in sorted(offers)]

        contributions: list[PublicMessage] = []
        selected_names = {cap.name for cap in selected}
        for capability in self.contributors:
            offer = offers.get(capability.name)
            if capability.name not in selected_names:
                trace.executions.append(
                    ExecutionRecord(
                        capability=capability.name,
                        role=capability.role.value,
                        offered_relevance=offer.relevance if offer else None,
                        offered_cost=offer.estimated_cost if offer else None,
                        selected=False,
                    )
                )
                continue

            started = perf_counter()
            try:
                result = capability.run(base_context)
            except Exception as exc:
                result = CapabilityResult(
                    success=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            latency_ms = (perf_counter() - started) * 1000.0
            contributions.extend(result.messages)
            self.memory.update_active(result.active_state_updates)
            self.memory.update_semantic(result.semantic_updates)
            self.memory.record_capability(
                capability.name,
                success=result.success,
                cost=result.measured_cost,
            )
            trace.executions.append(
                ExecutionRecord(
                    capability=capability.name,
                    role=capability.role.value,
                    offered_relevance=offer.relevance if offer else None,
                    offered_cost=offer.estimated_cost if offer else None,
                    selected=True,
                    success=result.success,
                    measured_cost=result.measured_cost,
                    latency_ms=latency_ms,
                    error=result.error,
                )
            )

        composer_context = self._context(user_text, contributions)
        started = perf_counter()
        try:
            composed = self.composer.run(composer_context)
        except Exception as exc:
            composed = CapabilityResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        latency_ms = (perf_counter() - started) * 1000.0
        self.memory.update_active(composed.active_state_updates)
        self.memory.update_semantic(composed.semantic_updates)
        self.memory.record_capability(
            self.composer.name,
            success=composed.success,
            cost=composed.measured_cost,
        )
        trace.executions.append(
            ExecutionRecord(
                capability=self.composer.name,
                role=self.composer.role.value,
                offered_relevance=None,
                offered_cost=None,
                selected=True,
                success=composed.success,
                measured_cost=composed.measured_cost,
                latency_ms=latency_ms,
                error=composed.error,
            )
        )

        response = ""
        for message in composed.messages:
            if message.kind == "assistant_text":
                response = str(message.content)
                trace.response_metadata = dict(message.metadata)
                break
        if not response and composed.error:
            response = "I could not compose a response."

        trace.response = response
        self.memory.append_episode(
            {"turn": self.turn_id, "role": "assistant", "text": response}
        )
        return response, trace

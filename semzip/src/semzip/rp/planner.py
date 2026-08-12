from __future__ import annotations

from .model import CharacterMind, Event, ResponsePlan, atom
from .world import World


class CharacterPlanner:
    """Small utility/rule planner that produces semantic response plans, not prose."""

    def plan_for_event(self, mind: CharacterMind, event: Event, world: World) -> ResponsePlan:
        speaker = atom(mind.name)

        if not event.succeeded:
            if event.reason == "unknown_object":
                return ResponsePlan.build(
                    speaker,
                    "correct",
                    "reject_false_world_assumption",
                    content={"object": event.object_id or "that", "reason": "does_not_exist"},
                    emotion=("skeptical",),
                    actions=("raises an eyebrow",),
                    style=self._style(mind),
                )
            if event.reason == "not_co_located":
                return ResponsePlan.build(
                    speaker,
                    "correct",
                    "reject_impossible_action",
                    content={"reason": "not_co_located"},
                    emotion=("dry",),
                    style=self._style(mind),
                )
            return ResponsePlan.build(
                speaker,
                "refuse",
                "reject_failed_action",
                content={"reason": event.reason or "invalid"},
                style=self._style(mind),
            )

        if event.kind == "take" and event.target == speaker:
            protect_weight = max((g.weight for g in mind.goals if atom(g.name) == "protect_secret"), default=0.0)
            object_id = event.object_id or "object"
            if protect_weight >= 0.7:
                return ResponsePlan.build(
                    speaker,
                    "confront",
                    "recover_object_without_revealing_secret",
                    content={"object": object_id, "request": "give_it_back"},
                    emotion=("irritated", "guarded"),
                    actions=("her expression hardens",),
                    style=self._style(mind),
                )
            return ResponsePlan.build(
                speaker,
                "demand",
                "recover_property",
                content={"object": object_id, "request": "give_it_back"},
                emotion=("annoyed",),
                style=self._style(mind),
            )

        return ResponsePlan.build(
            speaker,
            "acknowledge",
            "continue_scene",
            content={"event": event.kind},
            style=self._style(mind),
        )

    def answer_fact_question(
        self,
        mind: CharacterMind,
        subject: str,
        dimension: str,
        world: World,
        *,
        requester: str = "user",
    ) -> ResponsePlan:
        subject, dimension = atom(subject), atom(dimension)
        key = (subject, dimension)
        belief = mind.belief(subject, dimension)
        is_secret = key in mind.secrets

        if is_secret:
            return ResponsePlan.build(
                mind.name,
                "evade",
                "conceal_secret",
                content={"subject": subject, "dimension": dimension},
                emotion=("guarded", "amused"),
                actions=("watches you carefully",),
                style=self._style(mind),
            )

        if belief is None or belief.value is None:
            return ResponsePlan.build(
                mind.name,
                "admit_uncertainty",
                "avoid_inventing_fact",
                content={"subject": subject, "dimension": dimension},
                style=self._style(mind),
            )

        return ResponsePlan.build(
            mind.name,
            "inform",
            "answer_from_belief",
            content={"subject": subject, "dimension": dimension, "value": belief.value},
            style=self._style(mind),
        )

    def respond_to_memory_claim(
        self,
        mind: CharacterMind,
        *,
        claim_token: str,
        requester: str = "user",
    ) -> ResponsePlan:
        token = atom(claim_token)
        matching = [m for m in mind.memories if m.kind == "speech" and token in atom(m.summary)]
        if not matching:
            return ResponsePlan.build(
                mind.name,
                "correct",
                "reject_false_memory_claim",
                content={"claim": claim_token},
                emotion=("skeptical",),
                actions=("gives you a doubtful look",),
                style=self._style(mind),
            )
        return ResponsePlan.build(
            mind.name,
            "acknowledge",
            "confirm_memory",
            content={"claim": claim_token},
            style=self._style(mind),
        )

    @staticmethod
    def _style(mind: CharacterMind) -> tuple[str, ...]:
        style: list[str] = []
        if mind.traits.get("sarcastic", 0.0) >= 0.6:
            style.append("sarcastic")
        if mind.traits.get("proud", 0.0) >= 0.6:
            style.append("confident")
        if mind.traits.get("suspicious", 0.0) >= 0.6:
            style.append("guarded")
        return tuple(style)

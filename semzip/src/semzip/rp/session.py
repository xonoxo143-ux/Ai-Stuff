from __future__ import annotations

import re

from .mind import observe_event, sync_initial_observation
from .model import CharacterMind, Goal, ResponsePlan, atom
from .planner import CharacterPlanner
from .realizer import CheapRealizer
from .world import World


class UnsupportedInput(ValueError):
    pass


class RPSession:
    """Small complete RP loop for architectural experiments."""

    _TAKE_YOUR = re.compile(r"^i (?:take|grab|snatch) your (?P<object>[a-z][a-z0-9_ -]*)[.!?]*$", re.I)
    _TAKE = re.compile(r"^i (?:take|grab|snatch) (?:the )?(?P<object>[a-z][a-z0-9_ -]*)[.!?]*$", re.I)
    _WHERE = re.compile(r"^(?:where is|where's) (?:the )?(?P<object>[a-z][a-z0-9_ -]*)[?!.]*$", re.I)
    _WHO_HAS = re.compile(r"^who (?:has|is carrying) (?:the )?(?P<object>[a-z][a-z0-9_ -]*)[?!.]*$", re.I)
    _BEHIND = re.compile(r"^what(?:'s| is) (?:behind|in) (?:the )?(?P<place>[a-z][a-z0-9_ -]*)[?!.]*$", re.I)
    _FALSE_TOLD = re.compile(r"^you told me .*?(?P<token>basement|key|documents|letter|secret).*?[.!?]*$", re.I)

    def __init__(
        self,
        world: World,
        character: CharacterMind,
        *,
        user_name: str = "user",
        planner: CharacterPlanner | None = None,
        realizer: CheapRealizer | None = None,
    ) -> None:
        self.world = world
        self.character = character
        self.user_name = atom(user_name)
        self.planner = planner or CharacterPlanner()
        self.realizer = realizer or CheapRealizer()

    @classmethod
    def yvette_demo(cls) -> "RPSession":
        world = World()
        world.create_entity("user", "character", location="study")
        world.create_entity("yvette", "character", location="study")
        world.create_entity("dagger", "item", location="study", owner="yvette", possessor="yvette")
        world.create_entity("key", "item", location="study", owner="yvette", possessor="yvette")
        world.create_entity("basement", "room")
        world.establish("basement", "contents", "stolen_documents")
        world.establish("key", "opens", "basement")
        world.establish("yvette", "injury_left_hand", "true")

        yvette = CharacterMind(
            "yvette",
            traits={"suspicious": 0.85, "sarcastic": 0.8, "proud": 0.75},
            goals=[
                Goal("protect_secret", 0.95, "basement"),
                Goal("determine_user_knowledge", 0.7, "user"),
            ],
        )
        sync_initial_observation(yvette, world)
        # Private knowledge is deliberately inserted into Yvette's mind only.
        yvette.believe("basement", "contents", "stolen_documents")
        yvette.believe("key", "opens", "basement")
        yvette.secrets.add(("basement", "contents"))
        yvette.secrets.add(("key", "opens"))
        return cls(world, yvette)

    def process(self, text: str) -> tuple[ResponsePlan, str]:
        normalized = " ".join(text.strip().split())

        if match := self._TAKE_YOUR.fullmatch(normalized):
            object_id = atom(match.group("object"))
            event = self.world.take(self.user_name, object_id, from_actor=self.character.name)
            observe_event(self.character, event, self.world)
            plan = self.planner.plan_for_event(self.character, event, self.world)
            return plan, self.realizer.realize(plan)

        if match := self._TAKE.fullmatch(normalized):
            object_id = atom(match.group("object"))
            event = self.world.take(self.user_name, object_id)
            observe_event(self.character, event, self.world)
            plan = self.planner.plan_for_event(self.character, event, self.world)
            return plan, self.realizer.realize(plan)

        if match := self._WHERE.fullmatch(normalized):
            object_id = atom(match.group("object"))
            plan = self.planner.answer_fact_question(
                self.character, object_id, "location", self.world, requester=self.user_name
            )
            return plan, self.realizer.realize(plan)

        if match := self._WHO_HAS.fullmatch(normalized):
            object_id = atom(match.group("object"))
            plan = self.planner.answer_fact_question(
                self.character, object_id, "possessor", self.world, requester=self.user_name
            )
            return plan, self.realizer.realize(plan)

        if match := self._BEHIND.fullmatch(normalized):
            place = atom(match.group("place"))
            plan = self.planner.answer_fact_question(
                self.character, place, "contents", self.world, requester=self.user_name
            )
            return plan, self.realizer.realize(plan)

        if match := self._FALSE_TOLD.fullmatch(normalized):
            plan = self.planner.respond_to_memory_claim(
                self.character, claim_token=match.group("token"), requester=self.user_name
            )
            return plan, self.realizer.realize(plan)

        raise UnsupportedInput(f"RP Kernel 0.1 cannot safely interpret: {text!r}")

from __future__ import annotations

from .model import ResponsePlan


class CheapRealizer:
    """Deterministic construction-based renderer for RP Kernel 0.1."""

    def realize(self, plan: ResponsePlan) -> str:
        action = ""
        if plan.actions:
            action = f"{plan.speaker.title()} {plan.actions[0]}. "

        intent = plan.intent
        style = set(plan.style)

        if intent == "reject_false_world_assumption":
            obj = (plan.value("object") or "that").replace("_", " ")
            if "sarcastic" in style:
                speech = f'“Interesting trick. There is no {obj} here to take.”'
            else:
                speech = f'“There is no {obj} here.”'
            return action + speech

        if intent == "reject_impossible_action":
            return action + '“You are not close enough to do that.”'

        if intent == "recover_object_without_revealing_secret":
            obj = (plan.value("object") or "that").replace("_", " ")
            if "sarcastic" in style:
                speech = f'“Cute. Put the {obj} back.”'
            else:
                speech = f'“Give me the {obj} back.”'
            return action + speech

        if intent == "recover_property":
            obj = (plan.value("object") or "that").replace("_", " ")
            return action + f'“Give me the {obj} back.”'

        if intent == "conceal_secret":
            if "sarcastic" in style:
                speech = '“It is nothing you need to concern yourself with.”'
            else:
                speech = '“I would rather not discuss that.”'
            return action + speech

        if intent == "avoid_inventing_fact":
            return action + '“I do not know.”'

        if intent == "answer_from_belief":
            subject = (plan.value("subject") or "it").replace("_", " ")
            dimension = (plan.value("dimension") or "state").replace("_", " ")
            value = (plan.value("value") or "unknown").replace("_", " ")
            return action + f'“As far as I know, {subject}’s {dimension} is {value}.”'

        if intent == "reject_false_memory_claim":
            if "sarcastic" in style:
                return action + '“That is a creative memory. It is not one of mine.”'
            return action + '“I do not remember saying that.”'

        if intent == "confirm_memory":
            return action + '“Yes. I remember.”'

        if intent == "continue_scene":
            return action + '“Go on.”'

        return action + '“No.”'

import unittest

from semzip.vm_actions import ActionSchema, Parameter
from semzip.vm_effects import ShiftEffect
from semzip.vm_patch import SemanticPatch
from semzip.vm_plan import Goal, SymbolicPlanner
from semzip.vm_state import StateSnapshot
from semzip.vm_transform import SemanticTransform


class GenericPlannerTests(unittest.TestCase):
    def test_planner_accepts_schema_with_no_lexical_action_function(self):
        def build(bindings):
            return SemanticTransform.build(
                SemanticPatch.build(effects=(
                    ShiftEffect.build(
                        bindings["thing"],
                        "charge",
                        bindings["before"],
                        bindings["after"],
                    ),
                ))
            )

        schema = ActionSchema(
            "anonymous_charge_transition",
            (
                Parameter("thing", "things"),
                Parameter("before", "levels"),
                Parameter("after", "levels"),
            ),
            build,
            lambda b, _s: b["before"] != b["after"],
        )
        planner = SymbolicPlanner(
            schemas=(schema,),
            domains={"things": ("cell",), "levels": ("low", "high")},
        )
        result = planner.plan(
            StateSnapshot.build({("cell", "charge"): "low"}),
            Goal("cell", "charge", "high"),
            max_depth=1,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.steps[0].schema, "anonymous_charge_transition")
        self.assertEqual(result.steps[0].program.instructions[0].opcode, "K1")

    def test_snapshot_simulation_is_pure(self):
        start = StateSnapshot.build({("x", "state"): "a"})
        transform = SemanticTransform.build(
            SemanticPatch.build(effects=(ShiftEffect.build("x", "state", "a", "b"),))
        )
        after = start.apply(transform)
        self.assertEqual(start.get("x", "state"), "a")
        self.assertEqual(after.get("x", "state"), "b")

    def test_legacy_toy_constructor_still_solves_multistep_location_goal(self):
        planner = SymbolicPlanner(
            agents=("john",),
            rooms=("r0", "r1", "r2", "r3"),
            connections=(("r0", "r1"), ("r1", "r2"), ("r2", "r3")),
        )
        initial = StateSnapshot.build({
            ("key", "owner"): "john",
            ("key", "possessor"): "john",
            ("key", "location"): "r0",
        })
        result = planner.plan(initial, Goal("key", "location", "r3"), max_depth=4)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.steps), 3)
        self.assertTrue(all(step.schema == "shift_location" for step in result.steps))


if __name__ == "__main__":
    unittest.main()

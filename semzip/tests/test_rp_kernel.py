import unittest

from semzip.rp import CharacterMind, RPSession, World
from semzip.rp.mind import observe_event, sync_initial_observation


class WorldLedgerTests(unittest.TestCase):
    def test_failed_action_is_recorded_but_does_not_mutate_world(self):
        session = RPSession.yvette_demo()
        before = dict(session.world.facts)
        plan, _ = session.process("I take your sword.")
        self.assertEqual(plan.intent, "reject_false_world_assumption")
        self.assertEqual(before, session.world.facts)
        self.assertFalse(session.world.events[-1].succeeded)
        self.assertEqual(session.world.events[-1].reason, "unknown_object")

    def test_take_changes_possession_not_ownership(self):
        session = RPSession.yvette_demo()
        session.process("I take your key.")
        self.assertEqual(session.world.fact("key", "possessor"), "user")
        self.assertEqual(session.world.fact("key", "owner"), "yvette")

    def test_carried_object_moves_with_possessor(self):
        session = RPSession.yvette_demo()
        session.process("I take your key.")
        session.world.move("user", "hall")
        self.assertEqual(session.world.fact("user", "location"), "hall")
        self.assertEqual(session.world.fact("key", "location"), "hall")

    def test_event_ledger_is_permanent(self):
        session = RPSession.yvette_demo()
        session.process("I take your key.")
        take = session.world.events[-1]
        for i in range(100):
            session.world.set_fact("system", "user", "turn_marker", str(i))
        self.assertIn(take, session.world.events)
        self.assertEqual(session.world.fact("key", "possessor"), "user")


class MindSeparationTests(unittest.TestCase):
    def test_witness_updates_belief_and_relationship(self):
        session = RPSession.yvette_demo()
        trust_before = session.character.relation("user", "trust")
        session.process("I take your key.")
        self.assertTrue(session.character.knows("key", "possessor", "user"))
        self.assertLess(session.character.relation("user", "trust"), trust_before)
        self.assertTrue(any("took key from me" in m.summary for m in session.character.memories))

    def test_departure_is_perceived_from_source_room_and_carried_object_follows_in_belief(self):
        session = RPSession.yvette_demo()
        session.process("I take your key.")
        event = session.world.move("user", "hall")
        observe_event(session.character, event, session.world)
        self.assertTrue(session.character.knows("user", "location", "hall"))
        self.assertTrue(session.character.knows("key", "location", "hall"))

    def test_non_witness_does_not_gain_knowledge(self):
        world = World()
        world.create_entity("user", "character", location="study")
        world.create_entity("yvette", "character", location="study")
        world.create_entity("bob", "character", location="garden")
        world.create_entity("key", "item", location="study", owner="yvette", possessor="yvette")
        bob = CharacterMind("bob")
        sync_initial_observation(bob, world)
        event = world.take("user", "key", from_actor="yvette")
        observe_event(bob, event, world)
        self.assertFalse(bob.knows("key", "possessor", "user"))
        self.assertEqual(bob.memories, [])

    def test_secret_is_knowledge_not_public_world_access(self):
        session = RPSession.yvette_demo()
        self.assertTrue(session.character.knows("basement", "contents", "stolen_documents"))
        plan, text = session.process("What's in the basement?")
        self.assertEqual(plan.intent, "conceal_secret")
        self.assertNotIn("stolen", text.casefold())
        self.assertNotIn("documents", text.casefold())

    def test_false_conversational_memory_is_rejected(self):
        session = RPSession.yvette_demo()
        session.process("I take your key.")
        plan, _ = session.process("You told me about the key.")
        self.assertEqual(plan.intent, "reject_false_memory_claim")

    def test_unknown_fact_is_not_invented(self):
        session = RPSession.yvette_demo()
        session.world.create_entity("coin", "item", owner="user")
        plan, text = session.process("Where is the coin?")
        self.assertEqual(plan.intent, "avoid_inventing_fact")
        self.assertIn("do not know", text.casefold())


class PlanningTests(unittest.TestCase):
    def test_theft_response_protects_secret_without_leaking_it(self):
        session = RPSession.yvette_demo()
        plan, text = session.process("I grab your key.")
        self.assertEqual(plan.intent, "recover_object_without_revealing_secret")
        self.assertIn("guarded", plan.emotion)
        self.assertNotIn("basement", text.casefold())
        self.assertNotIn("documents", text.casefold())

    def test_plan_exists_before_realization(self):
        session = RPSession.yvette_demo()
        plan, text = session.process("I take your sword.")
        self.assertEqual(plan.speech_act, "correct")
        self.assertEqual(plan.intent, "reject_false_world_assumption")
        self.assertIsInstance(text, str)
        self.assertTrue(text)

    def test_personality_affects_style_not_world_truth(self):
        session = RPSession.yvette_demo()
        plan, text = session.process("I take your sword.")
        self.assertIn("sarcastic", plan.style)
        self.assertEqual(plan.value("reason"), "does_not_exist")
        self.assertIn("no sword", text.casefold())


class LongDelayTests(unittest.TestCase):
    def test_character_remembers_theft_after_unrelated_events(self):
        session = RPSession.yvette_demo()
        session.process("I take your key.")
        for i in range(100):
            session.world.set_fact("system", "user", "turn_marker", str(i))
        self.assertTrue(session.character.knows("key", "possessor", "user"))
        self.assertTrue(any(m.salience >= 0.9 and "key" in m.summary for m in session.character.memories))


if __name__ == "__main__":
    unittest.main()

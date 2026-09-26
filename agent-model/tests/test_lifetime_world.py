import torch

from agent_ecology.curriculum import ProgramCurriculumConfig
from agent_ecology.lifetime_world import (
    LifetimeWorld,
    LifetimeWorldConfig,
    targets_for_program,
)


def small_world(seed: int = 17) -> LifetimeWorld:
    return LifetimeWorld(
        LifetimeWorldConfig(
            total_experiences=1_000,
            sequence_length=6,
            seed=seed,
        )
    )


def test_random_access_replay_is_exact():
    world = small_world()
    first = world.experience(437)
    second = world.experience(437)

    assert first.family_id == second.family_id
    assert first.hidden_regime == second.hidden_regime
    assert first.hidden_rules == second.hidden_rules
    assert torch.equal(first.events, second.events)
    assert torch.equal(first.targets, second.targets)
    assert torch.equal(first.op_ids, second.op_ids)


def test_iteration_matches_random_access():
    world = small_world()
    sequential = list(world.iter_from(120, 125))

    for offset, experience in enumerate(sequential):
        direct = world.experience(120 + offset)
        assert experience.family_id == direct.family_id
        assert torch.equal(experience.events, direct.events)
        assert torch.equal(experience.targets, direct.targets)
        assert torch.equal(experience.op_ids, direct.op_ids)


def test_different_seed_changes_experience():
    left = small_world(seed=1).experience(333)
    right = small_world(seed=2).experience(333)

    assert not (
        torch.equal(left.events, right.events)
        and torch.equal(left.targets, right.targets)
    )


def test_expected_regime_order_and_return():
    world = small_world()

    assert world.regime_for(50).name == "foundation"
    assert world.regime_for(150).name == "family_expansion_a"
    assert world.regime_for(300).name == "interaction_a"
    assert world.regime_for(450).name == "recombination_a"
    assert world.regime_for(600).name == "return_with_decoy"
    assert world.regime_for(775).name == "family_expansion_b"
    assert world.regime_for(925).name == "mixed_return"


def test_family_context_is_visible_but_regime_is_not_a_channel():
    world = small_world()
    experience = world.experience(925)

    base_dim = ProgramCurriculumConfig().event_dim
    assert experience.events.shape[-1] == base_dim + 8

    family_slice = experience.events[:, base_dim:]
    assert torch.allclose(
        family_slice.sum(dim=-1),
        torch.ones(experience.events.shape[0]),
    )
    assert torch.all(
        torch.argmax(family_slice, dim=-1) == experience.family_id
    )

    # Hidden regime/rules remain Python evaluator metadata. No additional
    # regime channels exist beyond the fixed base+family schema.
    assert experience.hidden_regime == "mixed_return"
    assert "gain_add" in experience.hidden_rules


def test_decoy_phase_does_not_add_hidden_target_rule():
    world = small_world()
    experience = world.experience(600)

    arg_column = len(ProgramCurriculumConfig().event_dim * [0]) - 3
    # The base curriculum's argument column is len(OPS), which is event_dim-3.
    arg_column = ProgramCurriculumConfig().event_dim - 3
    recomputed = targets_for_program(
        experience.op_ids,
        experience.events[:, arg_column],
        rules=(),
        family_id=experience.family_id,
    )
    assert experience.hidden_rules == ()
    assert torch.equal(experience.targets, recomputed)


def test_late_lifetime_exposes_all_family_ids_across_samples():
    world = small_world()
    seen = {
        world.experience(index).family_id
        for index in range(850, 1_000)
    }
    assert seen == set(range(8))

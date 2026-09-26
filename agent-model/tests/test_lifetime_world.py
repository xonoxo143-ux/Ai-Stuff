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

    assert world.regime_for(50).name == "base"
    assert world.regime_for(150).name == "gain_add"
    assert world.regime_for(300).name == "mul_neg_interaction"
    assert world.regime_for(450).name == "gain_plus_mul_neg"
    assert world.regime_for(600).name == "base_with_decoy"
    assert world.regime_for(775).name == "square_half_interaction"
    assert world.regime_for(925).name == "gain_plus_square_half"


def test_hidden_regime_does_not_expand_agent_event_schema():
    world = small_world()
    experience = world.experience(925)

    assert experience.events.shape[-1] == ProgramCurriculumConfig().event_dim
    assert "gain_add" in experience.hidden_rules
    assert experience.hidden_regime == "gain_plus_square_half"


def test_decoy_phase_uses_base_target_dynamics():
    world = small_world()
    experience = world.experience(600)

    arg_column = len(experience.events[0]) - 3
    recomputed = targets_for_program(
        experience.op_ids,
        experience.events[:, arg_column],
        rules=(),
    )
    assert experience.hidden_rules == ()
    assert torch.equal(experience.targets, recomputed)

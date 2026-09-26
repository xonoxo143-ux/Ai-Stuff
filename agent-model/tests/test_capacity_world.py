import torch

from agent_ecology.capacity_world import CapacityWorld, CapacityWorldConfig
from agent_ecology.v1_capacity_sweep import summarize


def test_capacity_world_replay_is_exact():
    world = CapacityWorld(
        CapacityWorldConfig(
            num_families=16,
            experiences_per_family=8,
            sequence_length=4,
            seed=19,
        )
    )
    a = world.experience(77)
    b = world.experience(77)

    assert a.family_id == b.family_id
    assert a.phase == b.phase
    assert torch.equal(a.events, b.events)
    assert torch.equal(a.targets, b.targets)


def test_capacity_world_interface_width_does_not_scale_with_families():
    small = CapacityWorldConfig(num_families=8)
    large = CapacityWorldConfig(num_families=64)

    assert small.event_dim == large.event_dim
    assert small.event_dim == 19


def test_capacity_world_family_codes_and_dynamics_are_distinct():
    world = CapacityWorld(
        CapacityWorldConfig(num_families=8, seed=23)
    )

    left = world.family(0)
    right = world.family(1)

    assert not torch.allclose(left.code, right.code)
    assert not torch.allclose(left.a, right.a)
    assert not torch.allclose(left.readout, right.readout)


def test_capacity_world_phases_expand_and_return():
    world = CapacityWorld(
        CapacityWorldConfig(
            num_families=16,
            experiences_per_family=10,
        )
    )
    assert world.phase_for(10) == "foundation"
    assert world.phase_for(50) == "expansion"
    assert world.phase_for(100) == "novel_only"
    assert world.phase_for(150) == "mixed_return"


def _row(families, seed, control, loss, late):
    return {
        "family_count": families,
        "world_seed": seed,
        "control": control,
        "mean_task_loss": loss,
        "late_mixed_loss": late,
    }


def test_capacity_summary_preserves_direction():
    runs = [
        _row(8, 1, "fixed16", 1.0, 1.0),
        _row(8, 1, "sparse64", 0.8, 0.7),
        _row(8, 1, "dense64", 0.9, 0.8),
        _row(8, 2, "fixed16", 1.0, 1.0),
        _row(8, 2, "sparse64", 1.1, 0.9),
        _row(8, 2, "dense64", 1.2, 1.1),
    ]
    result = summarize(runs)["by_family_count"]["8"]

    assert result["pairs"] == 2
    assert result["sparse64_wins_overall"] == 1
    assert result["sparse64_wins_late"] == 2
    assert abs(result["mean_sparse64_minus_fixed16"] + 0.05) < 1e-9

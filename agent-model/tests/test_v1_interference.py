import torch

from agent_ecology.capacity_world import CapacityWorldConfig
from agent_ecology.interference_world import BlockedFamilyWorld
from agent_ecology.v1_interference import run_one, summarize


def test_blocked_family_world_is_exact_and_streams_are_disjoint():
    world = BlockedFamilyWorld(
        CapacityWorldConfig(
            num_families=8,
            sequence_length=3,
            seed=123,
        )
    )

    a = world.sample(3, 7, stream=0)
    b = world.sample(3, 7, stream=0)
    held_out = world.sample(3, 7, stream=1)

    assert torch.equal(a.events, b.events)
    assert torch.equal(a.targets, b.targets)
    assert not (
        torch.equal(a.events, held_out.events)
        and torch.equal(a.targets, held_out.targets)
    )


def test_family_batch_uses_requested_family_code():
    world = BlockedFamilyWorld(
        CapacityWorldConfig(
            num_families=8,
            sequence_length=3,
            seed=8,
        )
    )
    events, targets = world.batch(5, 4, stream=1)

    assert events.shape == (4, 3, 19)
    assert targets.shape == (4, 3, 1)

    expected = world.base.family(5).code
    assert torch.allclose(
        events[:, :, world.config.base_event_dim:],
        expected.view(1, 1, -1).expand(4, 3, -1),
    )


def test_tiny_interference_run_produces_triangular_loss_matrix():
    result = run_one(
        control="fixed16",
        family_count=4,
        world_seed=9,
        model_seed=10,
        train_examples=2,
        eval_examples=2,
        sequence_length=2,
        state_dim=12,
        workspace_slots=2,
        signature_dim=8,
        message_dim=8,
        thought_steps=1,
        learning_rate=1e-3,
        balance_weight=0.0,
    )

    matrix = result["loss_matrix"]
    assert len(matrix) == 4
    for row in range(4):
        for col in range(4):
            if col <= row:
                assert matrix[row][col] is not None
            else:
                assert matrix[row][col] is None

    assert result["mean_average_forgetting"] >= 0.0
    assert len(result["usage_by_family"]) == 4
    assert len(result["private_cell_update_norm_by_family"]) == 4


def test_summary_direction_for_forgetting():
    base = {
        "family_count": 8,
        "world_seed": 1,
        "mean_retention_delta": 0.0,
        "loss_backward_transfer": 0.0,
        "mean_learning_gain": 1.0,
    }
    fixed = {
        **base,
        "control": "fixed16",
        "mean_average_forgetting": 0.3,
        "mean_final_loss": 1.0,
    }
    sparse = {
        **base,
        "control": "sparse64",
        "mean_average_forgetting": 0.1,
        "mean_final_loss": 0.8,
    }

    summary = summarize([fixed, sparse])["by_family_count"]["8"]

    assert abs(summary["mean_forgetting64_minus_16"] + 0.2) < 1e-9
    assert summary["sparse64_forgets_less_wins"] == 1
    assert summary["sparse64_final_loss_wins"] == 1

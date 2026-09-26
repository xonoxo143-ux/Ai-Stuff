from agent_ecology.v1_route_ceiling import (
    oracle_coalition,
    run_one,
)


def test_oracle_coalitions_have_expected_reuse():
    assert oracle_coalition(
        0, num_cells=16, active_cells=4
    ).tolist() == [0, 1, 2, 3]
    assert oracle_coalition(
        3, num_cells=16, active_cells=4
    ).tolist() == [12, 13, 14, 15]
    assert oracle_coalition(
        4, num_cells=16, active_cells=4
    ).tolist() == [0, 1, 2, 3]

    assert oracle_coalition(
        4, num_cells=64, active_cells=4
    ).tolist() == [16, 17, 18, 19]


def test_tiny_oracle_run_executes():
    result = run_one(
        control="oracle16",
        family_count=4,
        world_seed=7,
        model_seed=8,
        experiences_per_family=1,
        sequence_length=2,
        state_dim=12,
        workspace_slots=2,
        signature_dim=8,
        message_dim=8,
        thought_steps=1,
        learning_rate=1e-3,
        balance_weight=0.01,
    )
    assert result["routing"] == "oracle"
    assert result["mean_task_loss"] >= 0.0

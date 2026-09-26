from argparse import Namespace

from agent_ecology.v1_controls import control_shape, run_control


def test_control_shapes():
    assert control_shape("fixed16") == (16, 4)
    assert control_shape("sparse64") == (64, 4)
    assert control_shape("dense64") == (64, 64)


def test_tiny_fixed_control_runs(tmp_path):
    args = Namespace(
        control="fixed16",
        world_size=100,
        experiences=3,
        start=0,
        sequence_length=3,
        world_seed=5,
        model_seed=6,
        state_dim=12,
        workspace_slots=2,
        signature_dim=8,
        message_dim=8,
        thought_steps=1,
        learning_rate=1e-3,
        weight_decay=0.0,
        balance_weight=0.0,
        routing_noise_std=0.0,
        log_every=1,
        device="cpu",
        output=tmp_path / "control.json",
    )

    result = run_control(args)

    assert result["control"] == "fixed16"
    assert result["experiences"] == 3
    assert result["parameter_count"] > 0
    assert result["mean_task_loss"] >= 0.0
    assert (tmp_path / "control.json").exists()

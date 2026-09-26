from agent_ecology.v1_compare import summarize_runs


def _run(pair, control, loss, regime_loss):
    return {
        "pair_index": pair,
        "control": control,
        "world_seed": 90 + pair,
        "model_seed": 1700 + pair,
        "mean_task_loss": loss,
        "per_regime": {
            "x": {
                "count": 10,
                "mean_task_loss": regime_loss,
            }
        },
    }


def test_summarize_runs_is_paired_and_directional():
    runs = [
        _run(0, "fixed16", 1.0, 1.0),
        _run(0, "sparse64", 0.8, 0.7),
        _run(0, "dense64", 0.9, 0.9),
        _run(1, "fixed16", 0.7, 0.6),
        _run(1, "sparse64", 0.8, 0.7),
        _run(1, "dense64", 0.9, 0.8),
    ]

    summary = summarize_runs(runs)
    aggregate = summary["aggregate"]

    assert aggregate["num_pairs"] == 2
    assert aggregate["sparse64_wins_vs_fixed16"] == 1
    assert aggregate["sparse64_wins_vs_dense64"] == 2
    assert abs(aggregate["mean_sparse64_minus_fixed16"] + 0.05) < 1e-9
    assert abs(
        aggregate["mean_regime_sparse64_minus_fixed16"]["x"] + 0.1
    ) < 1e-9

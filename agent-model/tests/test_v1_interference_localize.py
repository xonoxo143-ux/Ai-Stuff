from agent_ecology.v1_interference_localize import (
    _anchor_families,
    run_one,
    summarize,
)


def test_anchor_families_are_bounded_and_include_recent():
    assert _anchor_families(7) == [0, 1, 3, 5, 7]
    assert _anchor_families(1) == [0, 1]


def test_tiny_localization_run_executes_all_interventions():
    result = run_one(
        control="fixed16",
        family_count=4,
        world_seed=21,
        model_seed=22,
        checkpoints_after=[1],
        train_examples=1,
        eval_examples=1,
        sequence_length=2,
        state_dim=12,
        workspace_slots=2,
        signature_dim=8,
        message_dim=8,
        thought_steps=1,
        learning_rate=1e-3,
        balance_weight=0.0,
    )

    assert len(result["checkpoints"]) == 1
    branches = result["checkpoints"][0]["branches"]
    names = {row["intervention"] for row in branches}
    assert names == {
        "baseline",
        "freeze_private",
        "freeze_router",
        "freeze_workspace",
        "freeze_shared",
    }


def test_localization_summary_preserves_protection_direction():
    run = {
        "control": "fixed16",
        "checkpoints": [
            {
                "after_family": 1,
                "branches": [
                    {
                        "intervention": "baseline",
                        "mean_old_damage": 0.2,
                        "new_learning_gain": 0.3,
                        "protection_vs_baseline": 0.0,
                        "learning_cost_vs_baseline": 0.0,
                    },
                    {
                        "intervention": "freeze_private",
                        "mean_old_damage": 0.1,
                        "new_learning_gain": 0.2,
                        "protection_vs_baseline": 0.1,
                        "learning_cost_vs_baseline": 0.1,
                    },
                    *[
                        {
                            "intervention": name,
                            "mean_old_damage": 0.2,
                            "new_learning_gain": 0.3,
                            "protection_vs_baseline": 0.0,
                            "learning_cost_vs_baseline": 0.0,
                        }
                        for name in (
                            "freeze_router",
                            "freeze_workspace",
                            "freeze_shared",
                        )
                    ],
                ],
            }
        ],
    }
    sparse = {**run, "control": "sparse64"}

    summary = summarize([run, sparse])
    private = summary["by_control"]["fixed16"]["aggregate"][
        "freeze_private"
    ]

    assert abs(private["mean_protection_vs_baseline"] - 0.1) < 1e-9
    assert abs(private["mean_learning_cost_vs_baseline"] - 0.1) < 1e-9

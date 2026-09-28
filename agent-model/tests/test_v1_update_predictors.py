import torch

from agent_ecology.v1_update_predictors import (
    _average_ranks,
    _cell_scores_from_grads,
    _spearman,
)


def _grad(rows):
    return torch.tensor(rows, dtype=torch.float32)


def test_average_ranks_handles_ties():
    assert _average_ranks([1.0, 3.0, 3.0, 2.0]) == [
        1.0, 3.5, 3.5, 2.0
    ]


def test_spearman_orders_identical_and_reversed():
    assert abs(_spearman([1, 2, 3], [1, 2, 3]) - 1.0) < 1e-9
    assert abs(_spearman([1, 2, 3], [3, 2, 1]) + 1.0) < 1e-9


def test_cell_scores_keep_conflict_direction():
    names = ("w_ih", "w_hh", "b_ih", "b_hh", "w_msg", "b_msg")
    old_loss = {}
    old_output = {}
    new_grad = {}

    for name in names:
        old_loss[name] = _grad([[1.0], [1.0]])
        old_output[name] = _grad([[2.0], [0.5]])
        new_grad[name] = _grad([[-1.0], [1.0]])

    scores = _cell_scores_from_grads(
        old_loss=old_loss,
        old_output=old_output,
        new_grad=new_grad,
        usage=[0.75, 0.25],
    )

    assert scores["gradient_conflict"][0] > 0.0
    assert scores["gradient_conflict"][1] == 0.0
    assert scores["usage_grad"][0] > scores["usage_grad"][1]
    assert (
        scores["output_sensitivity"][0]
        > scores["output_sensitivity"][1]
    )

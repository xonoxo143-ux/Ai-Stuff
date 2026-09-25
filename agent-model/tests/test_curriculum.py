import torch

from agent_ecology.curriculum import (
    OP_TO_ID,
    apply_op,
    held_out_bigrams,
    sample_program_batch,
)


def test_program_targets_match_explicit_execution():
    torch.manual_seed(9)
    events, targets, op_ids = sample_program_batch(
        batch_size=16,
        sequence_length=5,
    )

    register = torch.zeros(16)
    arg_column = len(OP_TO_ID)

    for t in range(5):
        register = apply_op(
            register,
            op_ids[:, t],
            events[:, t, arg_column],
        )
        assert torch.allclose(register, targets[:, t, 0])


def test_training_generator_omits_held_out_bigrams():
    torch.manual_seed(11)
    _, _, op_ids = sample_program_batch(
        batch_size=512,
        sequence_length=6,
        forbidden_bigrams=held_out_bigrams(),
    )

    forbidden = {
        (OP_TO_ID[a], OP_TO_ID[b])
        for a, b in held_out_bigrams()
    }
    for t in range(1, op_ids.shape[1]):
        pairs = zip(
            op_ids[:, t - 1].tolist(),
            op_ids[:, t].tolist(),
        )
        assert all(pair not in forbidden for pair in pairs)

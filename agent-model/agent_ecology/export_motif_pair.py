from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict

import numpy as np
import torch
from torch import Tensor, nn

from .compile_motif import PairComposite, collect_teacher_samples
from .export_onnx import load_checkpoint


class TeacherPairBoundary(nn.Module):
    """
    Exact source-pair computation at the promoted motif boundary.

    Input layout is the same one used to train PairComposite:
      left read, right read, event embedding,
      left state, right state, left route weight, right route weight.
    """

    def __init__(self, model, left: int, right: int):
        super().__init__()
        self.h = model.config.state_dim
        self.m = model.config.message_dim

        for prefix, cell in (("left", left), ("right", right)):
            self.register_buffer(
                f"{prefix}_w_ih", model.w_ih[cell].detach().clone()
            )
            self.register_buffer(
                f"{prefix}_w_hh", model.w_hh[cell].detach().clone()
            )
            self.register_buffer(
                f"{prefix}_b_ih", model.b_ih[cell].detach().clone()
            )
            self.register_buffer(
                f"{prefix}_b_hh", model.b_hh[cell].detach().clone()
            )
            self.register_buffer(
                f"{prefix}_w_msg", model.w_msg[cell].detach().clone()
            )
            self.register_buffer(
                f"{prefix}_b_msg", model.b_msg[cell].detach().clone()
            )

    def _cell(
        self,
        read: Tensor,
        event: Tensor,
        state: Tensor,
        weight: Tensor,
        prefix: str,
    ):
        w_ih = getattr(self, f"{prefix}_w_ih")
        w_hh = getattr(self, f"{prefix}_w_hh")
        b_ih = getattr(self, f"{prefix}_b_ih")
        b_hh = getattr(self, f"{prefix}_b_hh")
        w_msg = getattr(self, f"{prefix}_w_msg")
        b_msg = getattr(self, f"{prefix}_b_msg")

        cell_input = torch.cat([read, event], dim=-1)
        input_gates = torch.matmul(cell_input, w_ih.transpose(0, 1)) + b_ih
        hidden_gates = torch.matmul(state, w_hh.transpose(0, 1)) + b_hh

        i_r, i_z, i_n = input_gates.chunk(3, dim=-1)
        h_r, h_z, h_n = hidden_gates.chunk(3, dim=-1)

        reset = torch.sigmoid(i_r + h_r)
        update = torch.sigmoid(i_z + h_z)
        candidate = torch.tanh(i_n + reset * h_n)
        new_state = (1.0 - update) * candidate + update * state

        message = torch.tanh(
            torch.matmul(new_state, w_msg.transpose(0, 1)) + b_msg
        )
        message = message * weight

        return new_state - state, message

    def forward(self, x: Tensor) -> Tensor:
        h = self.h
        cursor = 0
        left_read = x[:, cursor : cursor + h]
        cursor += h
        right_read = x[:, cursor : cursor + h]
        cursor += h
        event = x[:, cursor : cursor + h]
        cursor += h
        left_state = x[:, cursor : cursor + h]
        cursor += h
        right_state = x[:, cursor : cursor + h]
        cursor += h
        left_weight = x[:, cursor : cursor + 1]
        cursor += 1
        right_weight = x[:, cursor : cursor + 1]

        left_delta, left_message = self._cell(
            left_read, event, left_state, left_weight, "left"
        )
        right_delta, right_message = self._cell(
            right_read, event, right_state, right_weight, "right"
        )

        return torch.cat(
            [left_delta, right_delta, left_message, right_message],
            dim=-1,
        )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_graph(
    module: nn.Module,
    sample: Tensor,
    path: Path,
) -> None:
    module.eval()
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        module,
        sample,
        path.as_posix(),
        input_names=["boundary"],
        output_names=["replacement"],
        dynamic_axes={
            "boundary": {0: "batch"},
            "replacement": {0: "batch"},
        },
        opset_version=18,
        do_constant_folding=True,
        dynamo=False,
    )


def verify_onnx(
    module: nn.Module,
    sample: Tensor,
    path: Path,
) -> float:
    import onnxruntime as ort

    with torch.no_grad():
        expected = module(sample).cpu().numpy()

    session = ort.InferenceSession(
        path.as_posix(),
        providers=["CPUExecutionProvider"],
    )
    actual = session.run(None, {"boundary": sample.cpu().numpy()})[0]
    return float(np.max(np.abs(expected - actual)))


def load_composite(checkpoint_path: Path) -> tuple[PairComposite, dict]:
    payload = torch.load(checkpoint_path, map_location="cpu")
    state = payload["state_dict"]
    composite = PairComposite(
        input_dim=int(payload["input_dim"]),
        target_dim=int(payload["target_dim"]),
        hidden_dim=int(payload["hidden_dim"]),
        x_mean=state["x_mean"],
        x_std=state["x_std"],
        y_mean=state["y_mean"],
        y_std=state["y_std"],
    )
    composite.load_state_dict(state)
    composite.eval()
    return composite, payload


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("agent_checkpoint")
    p.add_argument("motif_checkpoint")
    p.add_argument("--output-dir", default="artifacts/motif-phone")
    p.add_argument("--sample-count", type=int, default=64)
    args = p.parse_args()

    model = load_checkpoint(Path(args.agent_checkpoint)).eval()
    composite, payload = load_composite(Path(args.motif_checkpoint))

    left, right = map(int, payload["motif"])
    teacher = TeacherPairBoundary(model, left, right).eval()

    # Fresh operating-boundary samples, separate from compiler training and
    # probation seeds.
    x, y, collection = collect_teacher_samples(
        model,
        left=left,
        right=right,
        batches=8,
        batch_size=128,
        sequence_length=6,
        seed=509,
    )
    sample_count = min(args.sample_count, x.shape[0])
    samples = x[:sample_count].contiguous()

    with torch.no_grad():
        teacher_y = teacher(samples)
        teacher_target_error = float(
            (teacher_y - y[:sample_count]).abs().max().cpu()
        )
        student_y = composite(samples)
        student_teacher_mae = float(
            (student_y - teacher_y).abs().mean().cpu()
        )

    if teacher_target_error > 2e-5:
        raise RuntimeError(
            f"Teacher boundary reconstruction failed: {teacher_target_error}"
        )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    teacher_path = out_dir / "motif-1-10-teacher.onnx"
    student_path = out_dir / "motif-1-10-compiled.onnx"
    samples_path = out_dir / "motif-1-10-boundary-samples.f32"

    export_graph(teacher, samples[:2], teacher_path)
    export_graph(composite, samples[:2], student_path)

    teacher_onnx_error = verify_onnx(teacher, samples, teacher_path)
    student_onnx_error = verify_onnx(composite, samples, student_path)

    samples.cpu().numpy().astype("<f4").tofile(samples_path)

    manifest = {
        "schema": 1,
        "motif": [left, right],
        "input_dim": int(samples.shape[1]),
        "output_dim": int(teacher_y.shape[1]),
        "sample_count": sample_count,
        "sample_dtype": "float32-le",
        "teacher": {
            "file": teacher_path.name,
            "sha256": sha256(teacher_path),
            "onnx_max_abs_error": teacher_onnx_error,
        },
        "compiled": {
            "file": student_path.name,
            "sha256": sha256(student_path),
            "onnx_max_abs_error": student_onnx_error,
            "parameters": composite.parameter_count(),
        },
        "samples": {
            "file": samples_path.name,
            "sha256": sha256(samples_path),
        },
        "parity": {
            "teacher_reconstruction_max_abs_error": teacher_target_error,
            "compiled_mean_abs_delta_vs_teacher_on_phone_samples": (
                student_teacher_mae
            ),
        },
        "probation_summary": payload.get("probation_summary", {}),
        "fresh_sample_collection": collection,
    }

    manifest_path = out_dir / "motif-1-10-phone.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

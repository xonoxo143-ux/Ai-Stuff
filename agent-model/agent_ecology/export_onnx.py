from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict

import numpy as np
import torch
from torch import Tensor, nn

from .model import EcologyConfig, SparseRecurrentEcology


class ThoughtStepExport(nn.Module):
    def __init__(self, model: SparseRecurrentEcology):
        super().__init__()
        self.model = model

    def forward(
        self,
        event: Tensor,
        workspace: Tensor,
        cell_states: Tensor,
    ):
        return self.model.thought_step(
            event,
            workspace,
            cell_states,
            add_training_noise=False,
        )



class DenseThoughtStepExport(nn.Module):
    def __init__(self, model: SparseRecurrentEcology):
        super().__init__()
        self.model = model

    def forward(
        self,
        event: Tensor,
        workspace: Tensor,
        cell_states: Tensor,
    ):
        return self.model.thought_step_dense_reference(
            event,
            workspace,
            cell_states,
        )


def load_checkpoint(path: Path) -> SparseRecurrentEcology:
    payload = torch.load(path, map_location="cpu")
    config = EcologyConfig(**payload["config"])
    model = SparseRecurrentEcology(config)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model


def export_model(
    model: SparseRecurrentEcology,
    output_path: Path,
    *,
    verify: bool = True,
    dense_reference: bool = False,
) -> Dict[str, float]:
    model.eval()
    wrapper = (
        DenseThoughtStepExport(model)
        if dense_reference
        else ThoughtStepExport(model)
    ).eval()
    c = model.config

    event = torch.randn(2, c.event_dim)
    state = model.initial_state(2)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    input_names = ["event", "workspace", "cell_states"]
    output_names = [
        "output",
        "new_workspace",
        "new_cell_states",
        "selected_cells",
        "route_weights",
        "router_scores",
        "halt_probability",
    ]

    torch.onnx.export(
        wrapper,
        (event, state.workspace, state.cell_states),
        output_path.as_posix(),
        input_names=input_names,
        output_names=output_names,
        dynamic_axes={
            "event": {0: "batch"},
            "workspace": {0: "batch"},
            "cell_states": {0: "batch"},
            "output": {0: "batch"},
            "new_workspace": {0: "batch"},
            "new_cell_states": {0: "batch"},
            "selected_cells": {0: "batch"},
            "route_weights": {0: "batch"},
            "router_scores": {0: "batch"},
            "halt_probability": {0: "batch"},
        },
        opset_version=18,
        do_constant_folding=True,
        dynamo=False,
    )

    metrics: Dict[str, float] = {
        "onnx_bytes": float(output_path.stat().st_size)
    }

    if verify:
        import onnxruntime as ort

        with torch.no_grad():
            expected = wrapper(
                event, state.workspace, state.cell_states
            )

        session = ort.InferenceSession(
            output_path.as_posix(),
            providers=["CPUExecutionProvider"],
        )
        actual = session.run(
            None,
            {
                "event": event.numpy(),
                "workspace": state.workspace.detach().numpy(),
                "cell_states": state.cell_states.detach().numpy(),
            },
        )

        max_abs = 0.0
        for torch_value, ort_value in zip(expected, actual):
            reference = torch_value.detach().cpu().numpy()
            if np.issubdtype(reference.dtype, np.integer):
                if not np.array_equal(reference, ort_value):
                    raise RuntimeError("ONNX integer output parity failed")
                continue
            delta = float(np.max(np.abs(reference - ort_value)))
            max_abs = max(max_abs, delta)

        metrics["max_abs_error"] = max_abs
        if max_abs > 2e-4:
            raise RuntimeError(
                f"ONNX parity exceeded tolerance: {max_abs}"
            )

    return metrics


def write_manifest(
    model: SparseRecurrentEcology,
    onnx_path: Path,
    manifest_path: Path,
    metrics: Dict[str, float],
    *,
    dense_onnx_path: Path | None = None,
    dense_metrics: Dict[str, float] | None = None,
) -> None:
    digest = hashlib.sha256(onnx_path.read_bytes()).hexdigest()
    payload = {
        "schema": 2 if dense_onnx_path is not None else 1,
        "model_id": "agent-ecology-v0",
        "runtime": "onnxruntime",
        "format": "onnx",
        "onnx_file": onnx_path.name,
        "sha256": digest,
        "config": asdict(model.config),
        "initial_workspace": (
            model.initial_workspace.detach().cpu().float().tolist()
        ),
        "initial_cell_state": "zeros",
        "inputs": ["event", "workspace", "cell_states"],
        "outputs": [
            "output",
            "new_workspace",
            "new_cell_states",
            "selected_cells",
            "route_weights",
            "router_scores",
            "halt_probability",
        ],
        "export_metrics": metrics,
    }
    if dense_onnx_path is not None:
        payload["dense_reference"] = {
            "onnx_file": dense_onnx_path.name,
            "sha256": hashlib.sha256(dense_onnx_path.read_bytes()).hexdigest(),
            "export_metrics": dense_metrics or {},
            "semantics": "all-cell candidate compute; same top-k commit and messages",
        }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("checkpoint")
    p.add_argument(
        "--output",
        default="artifacts/agent-ecology-thought-step.onnx",
    )
    p.add_argument("--manifest", default=None)
    p.add_argument("--dense-output", default=None)
    p.add_argument("--skip-verify", action="store_true")
    args = p.parse_args()

    model = load_checkpoint(Path(args.checkpoint))
    output_path = Path(args.output)
    metrics = export_model(
        model,
        output_path,
        verify=not args.skip_verify,
        dense_reference=False,
    )

    dense_path = Path(args.dense_output) if args.dense_output else None
    dense_metrics = None
    if dense_path is not None:
        dense_metrics = export_model(
            model,
            dense_path,
            verify=not args.skip_verify,
            dense_reference=True,
        )

        # Verify the two execution paths are semantically equivalent before
        # packaging them for hardware comparison.
        event = torch.randn(4, model.config.event_dim)
        state = model.initial_state(4)
        with torch.no_grad():
            sparse = model.thought_step(
                event,
                state.workspace,
                state.cell_states,
                add_training_noise=False,
            )
            dense = model.thought_step_dense_reference(
                event,
                state.workspace,
                state.cell_states,
            )
        max_delta = 0.0
        for sparse_value, dense_value in zip(sparse, dense):
            if sparse_value.dtype in (torch.int32, torch.int64):
                if not torch.equal(sparse_value, dense_value):
                    raise RuntimeError(
                        "Sparse/dense selected-cell parity failed"
                    )
            else:
                max_delta = max(
                    max_delta,
                    float(
                        (sparse_value - dense_value)
                        .abs()
                        .max()
                        .cpu()
                    ),
                )
        if max_delta > 2e-4:
            raise RuntimeError(
                f"Sparse/dense semantic parity failed: {max_delta}"
            )
        metrics["dense_semantic_max_abs_error"] = max_delta
    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else output_path.with_suffix(".json")
    )
    write_manifest(
        model,
        output_path,
        manifest_path,
        metrics,
        dense_onnx_path=dense_path,
        dense_metrics=dense_metrics,
    )
    print(
        json.dumps(
            {
                **metrics,
                "manifest": manifest_path.as_posix(),
                "dense_output": (
                    dense_path.as_posix()
                    if dense_path is not None
                    else None
                ),
                "dense_metrics": dense_metrics,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
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
) -> Dict[str, float]:
    model.eval()
    wrapper = ThoughtStepExport(model).eval()
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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("checkpoint")
    p.add_argument(
        "--output",
        default="artifacts/agent-ecology-thought-step.onnx",
    )
    p.add_argument("--skip-verify", action="store_true")
    args = p.parse_args()

    model = load_checkpoint(Path(args.checkpoint))
    metrics = export_model(
        model,
        Path(args.output),
        verify=not args.skip_verify,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

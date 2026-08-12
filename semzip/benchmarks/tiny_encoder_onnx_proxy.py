from __future__ import annotations

import json
import statistics
import time
from pathlib import Path


def benchmark(session, feeds, *, warmup=20, iterations=200):
    for _ in range(warmup):
        session.run(None, feeds)
    samples = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        session.run(None, feeds)
        samples.append((time.perf_counter_ns() - start) / 1e6)
    samples.sort()
    return {
        "iterations": iterations,
        "median_ms": statistics.median(samples),
        "mean_ms": statistics.mean(samples),
        "p90_ms": samples[int(0.90 * (len(samples) - 1))],
        "p99_ms": samples[int(0.99 * (len(samples) - 1))],
    }


def main():
    import numpy as np
    import onnxruntime as ort
    import torch
    import torch.nn as nn
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(2)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    model_name = "google/bert_uncased_L-2_H-128_A-2"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    base = AutoModel.from_pretrained(model_name).eval()

    class Wrapper(nn.Module):
        def __init__(self, model):
            super().__init__()
            self.model = model

        def forward(self, input_ids, attention_mask, token_type_ids):
            return self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                token_type_ids=token_type_ids,
            ).last_hidden_state

    wrapper = Wrapper(base).eval()
    inputs = tokenizer(
        "After lunch Maya Chen temporarily handed the antique telescope to Priya and asked for it back tomorrow.",
        return_tensors="pt",
        truncation=True,
        max_length=64,
        padding="max_length",
    )
    if "token_type_ids" not in inputs:
        inputs["token_type_ids"] = torch.zeros_like(inputs["input_ids"])

    output_dir = Path("onnx-proxy")
    output_dir.mkdir(exist_ok=True)
    fp_path = output_dir / "tiny-encoder-fp32.onnx"
    int8_path = output_dir / "tiny-encoder-int8.onnx"

    torch.onnx.export(
        wrapper,
        (inputs["input_ids"], inputs["attention_mask"], inputs["token_type_ids"]),
        fp_path,
        input_names=("input_ids", "attention_mask", "token_type_ids"),
        output_names=("last_hidden_state",),
        dynamic_axes={
            "input_ids": {0: "batch", 1: "sequence"},
            "attention_mask": {0: "batch", 1: "sequence"},
            "token_type_ids": {0: "batch", 1: "sequence"},
            "last_hidden_state": {0: "batch", 1: "sequence"},
        },
        opset_version=17,
        do_constant_folding=True,
    )

    quantize_dynamic(
        fp_path,
        int8_path,
        weight_type=QuantType.QInt8,
        per_channel=True,
        reduce_range=False,
    )

    options = ort.SessionOptions()
    options.intra_op_num_threads = min(4, torch.get_num_threads())
    fp_session = ort.InferenceSession(
        str(fp_path), options, providers=["CPUExecutionProvider"]
    )
    int8_session = ort.InferenceSession(
        str(int8_path), options, providers=["CPUExecutionProvider"]
    )
    feeds = {
        key: value.detach().cpu().numpy().astype(np.int64)
        for key, value in inputs.items()
        if key in {"input_ids", "attention_mask", "token_type_ids"}
    }

    fp_output = fp_session.run(None, feeds)[0]
    q_output = int8_session.run(None, feeds)[0]
    fp_flat = fp_output.reshape(-1).astype(np.float64)
    q_flat = q_output.reshape(-1).astype(np.float64)
    cosine = float(
        np.dot(fp_flat, q_flat)
        / max(np.linalg.norm(fp_flat) * np.linalg.norm(q_flat), 1e-12)
    )
    mae = float(np.abs(fp_output - q_output).mean())

    fp_latency = benchmark(fp_session, feeds)
    q_latency = benchmark(int8_session, feeds)
    fp_bytes = fp_path.stat().st_size
    q_bytes = int8_path.stat().st_size

    report = {
        "model": model_name,
        "parameter_count": sum(p.numel() for p in base.parameters()),
        "sequence_length": int(inputs["input_ids"].shape[1]),
        "fp32_onnx_mb": fp_bytes / (1024 * 1024),
        "int8_onnx_mb": q_bytes / (1024 * 1024),
        "size_ratio_int8_over_fp32": q_bytes / fp_bytes,
        "fp32_ort_latency": fp_latency,
        "int8_ort_latency": q_latency,
        "latency_ratio_int8_over_fp32": q_latency["median_ms"] / fp_latency["median_ms"],
        "mean_absolute_output_error": mae,
        "flattened_output_cosine_similarity": cosine,
        "onnx_opset": 17,
        "caveat": (
            "ONNX Runtime CPU benchmark on a GitHub-hosted x86 machine. It validates "
            "portable export, quantized size, and relative CPU behavior only; Android ARM "
            "runtime/accelerator latency and thermals remain unmeasured."
        ),
    }
    Path("tiny-encoder-onnx-proxy.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

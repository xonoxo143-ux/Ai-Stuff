from __future__ import annotations

import io
import json
import statistics
import time
from pathlib import Path


def serialized_state_mb(model) -> float:
    import torch

    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return len(buffer.getvalue()) / (1024 * 1024)


def benchmark(model, inputs, *, warmup: int = 20, iterations: int = 200):
    import torch

    model.eval()
    with torch.inference_mode():
        for _ in range(warmup):
            model(**inputs)
        timings = []
        for _ in range(iterations):
            start = time.perf_counter_ns()
            model(**inputs)
            timings.append((time.perf_counter_ns() - start) / 1e6)
    timings.sort()
    return {
        "iterations": iterations,
        "median_ms": statistics.median(timings),
        "p90_ms": timings[int(0.90 * (len(timings) - 1))],
        "p99_ms": timings[int(0.99 * (len(timings) - 1))],
        "mean_ms": statistics.mean(timings),
    }


def main():
    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(1)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    model_name = "google/bert_uncased_L-2_H-128_A-2"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).eval()
    parameter_count = sum(p.numel() for p in model.parameters())

    text = (
        "After lunch Maya Chen temporarily handed the antique telescope to Priya "
        "and asked for it back tomorrow."
    )
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=64,
        padding="max_length",
    )

    with torch.inference_mode():
        fp_output = model(**inputs).last_hidden_state.detach()

    fp_size = serialized_state_mb(model)
    fp_latency = benchmark(model, inputs)

    # Dynamic weight-only int8 on Linear layers is a portable CPU-side proxy. It is
    # not claimed to match Android NNAPI/QNN/ExecuTorch performance.
    try:
        quantized = torch.ao.quantization.quantize_dynamic(
            model,
            {torch.nn.Linear},
            dtype=torch.qint8,
        ).eval()
        quantization_backend = "torch_dynamic_qint8_linear"
    except Exception as exc:
        raise RuntimeError(f"dynamic int8 quantization failed: {exc}") from exc

    with torch.inference_mode():
        q_output = quantized(**inputs).last_hidden_state.detach().float()
    q_size = serialized_state_mb(quantized)
    q_latency = benchmark(quantized, inputs)

    mae = float((fp_output - q_output).abs().mean())
    cosine = float(
        torch.nn.functional.cosine_similarity(
            fp_output.flatten().unsqueeze(0),
            q_output.flatten().unsqueeze(0),
        ).item()
    )

    report = {
        "model": model_name,
        "parameter_count": parameter_count,
        "sequence_length": int(inputs["input_ids"].shape[1]),
        "batch_size": 1,
        "threads": torch.get_num_threads(),
        "fp32_state_mb": fp_size,
        "int8_state_mb": q_size,
        "size_ratio_int8_over_fp32": q_size / fp_size,
        "fp32_latency": fp_latency,
        "int8_latency": q_latency,
        "latency_ratio_int8_over_fp32": q_latency["median_ms"] / fp_latency["median_ms"],
        "mean_absolute_output_error": mae,
        "flattened_output_cosine_similarity": cosine,
        "quantization_backend": quantization_backend,
        "caveat": (
            "GitHub-hosted x86 CPU proxy only. This measures relative model compactness "
            "and CPU behavior, not Android/ARM latency, thermals, or accelerator support."
        ),
    }
    Path("tiny-encoder-phone-proxy.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

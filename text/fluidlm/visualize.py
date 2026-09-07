from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="Render FluidLM flow diagnostics")
    parser.add_argument("trace", help="Path to trace.npz")
    parser.add_argument("--out", default="flow.png")
    args = parser.parse_args()

    trace = np.load(args.trace)
    density = trace["density"]
    vorticity = trace["vorticity"]
    kinetic = trace["kinetic"]

    if density.ndim != 3 or vorticity.ndim != 3:
        raise ValueError("Trace must contain [time, height, width] density/vorticity")

    mean_density = density.mean(axis=0)
    mean_abs_vorticity = np.abs(vorticity).mean(axis=0)

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    im0 = axes[0].imshow(mean_density, origin="lower")
    axes[0].set_title("Mean semantic density")
    fig.colorbar(im0, ax=axes[0], fraction=0.046)

    im1 = axes[1].imshow(mean_abs_vorticity, origin="lower")
    axes[1].set_title("Mean |vorticity|")
    fig.colorbar(im1, ax=axes[1], fraction=0.046)

    axes[2].plot(np.arange(len(kinetic)), kinetic)
    axes[2].set_title("Kinetic activity")
    axes[2].set_xlabel("Generated character")
    axes[2].set_ylabel("Mean velocity²")

    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180)
    print(f"saved {out}")


if __name__ == "__main__":
    main()

from __future__ import annotations

from compiler_delta_rich_corpus import generate_rich_delta_examples
import train_delta_compiler


if __name__ == "__main__":
    # Reuse the exact same model/training/evaluation machinery; only the training
    # curriculum changes. Evaluation remains the baseline held-out distribution.
    train_delta_compiler.generate_delta_examples = generate_rich_delta_examples
    train_delta_compiler.main()

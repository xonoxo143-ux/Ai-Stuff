from compiler_delta_contrast_corpus import generate_contrast_examples
import train_semantic_probe_compiler as runner

if __name__ == "__main__":
    runner.generate_delta_examples = generate_contrast_examples
    runner.main()

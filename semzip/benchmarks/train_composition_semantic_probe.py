from compiler_composition_corpus import generate_composition_examples
import train_semantic_probe_compiler as runner

if __name__ == "__main__":
    runner.generate_delta_examples = generate_composition_examples
    runner.main()

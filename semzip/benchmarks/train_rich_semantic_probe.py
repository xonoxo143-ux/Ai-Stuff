from compiler_delta_rich_corpus import generate_rich_delta_examples
import train_semantic_probe_compiler as runner

if __name__ == "__main__":
    runner.generate_delta_examples = generate_rich_delta_examples
    runner.main()

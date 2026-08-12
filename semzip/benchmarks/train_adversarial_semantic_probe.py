from compiler_delta_adversarial_corpus import generate_adversarial_examples
import train_semantic_probe_compiler as runner

if __name__ == "__main__":
    runner.generate_delta_examples = generate_adversarial_examples
    runner.main()

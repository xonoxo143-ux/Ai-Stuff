from semzip.rp import RPSession


def main() -> None:
    session = RPSession.yvette_demo()
    print("RP Kernel 0.1 demo. Ctrl-D/Ctrl-Z to exit.")
    while True:
        try:
            text = input("> ")
        except EOFError:
            break
        try:
            plan, reply = session.process(text)
        except Exception as exc:
            print(f"[unsupported] {exc}")
            continue
        print(reply)
        print(f"[plan] {plan.intent} / {plan.speech_act}")


if __name__ == "__main__":
    main()

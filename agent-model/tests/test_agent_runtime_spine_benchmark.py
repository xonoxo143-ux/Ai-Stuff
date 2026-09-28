from __future__ import annotations

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
import json
from threading import Thread

from agent_runtime.spine_benchmark import (
    run_suite,
    score,
)


class SmartFake(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(
            self.headers["Content-Length"]
        )
        payload = json.loads(
            self.rfile.read(length)
        )
        messages = payload["messages"]
        last = next(
            msg["content"]
            for msg in reversed(messages)
            if msg["role"] == "user"
        )
        systems = "\n".join(
            msg["content"]
            for msg in messages
            if msg["role"] == "system"
        )
        history = "\n".join(
            msg["content"]
            for msg in messages
        )

        if "BLUE" in last:
            answer = "BLUE"
        elif "youngest" in last:
            answer = "Carol"
        elif "capital of Japan" in last:
            answer = "Tokyo"
        elif "All but 9" in last:
            answer = "9"
        elif (
            last.strip()
            == "12345 * 6789"
        ):
            answer = (
                "83810205"
                if "arithmetic=83810205"
                in systems
                else "I don't know"
            )
        elif "favorite fruit" in last:
            answer = (
                "mango"
                if "favorite_fruit=mango"
                in systems
                else "unknown"
            )
        elif (
            "codeword" in last.lower()
            and "previous" in last.lower()
        ):
            answer = (
                "GLASSHARBOR"
                if "GLASSHARBOR"
                in history
                else "unknown"
            )
        else:
            answer = "OK"

        body = json.dumps(
            {
                "id": "fake",
                "choices": [
                    {
                        "message": {
                            "role":
                                "assistant",
                            "content":
                                answer,
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 2,
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)

    def log_message(
        self,
        fmt,
        *args,
    ):
        pass


def test_scorers():
    assert score(
        "BLUE",
        "BLUE",
        "exact",
    )
    assert not score(
        "BLUE!",
        "BLUE",
        "exact",
    )
    assert score(
        "The answer is Tokyo.",
        "Tokyo",
        "contains",
    )
    assert score(
        "83,810,205",
        "83810205",
        "number",
    )


def test_suite_detects_hybrid_value():
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        SmartFake,
    )
    Thread(
        target=httpd.serve_forever,
        daemon=True,
    ).start()
    try:
        result = run_suite(
            base_url=(
                "http://127.0.0.1:"
                f"{httpd.server_address[1]}"
            ),
            model="fake",
            repeats=1,
            max_tokens=32,
        )
        assert (
            result["summary"]
            ["baseline"]["passes"]
            == 5
        )
        assert (
            result["summary"]
            ["baseline"]["automatic_cases"]
            == 6
        )
        assert (
            result["summary"]
            ["hybrid"]["passes"]
            == 7
        )
        assert (
            result["summary"]
            ["hybrid"]["automatic_cases"]
            == 7
        )
        arithmetic = next(
            row
            for row in result["rows"]
            if (
                row["mode"] == "hybrid"
                and row["case"]
                == "large_arithmetic"
            )
        )
        assert arithmetic["passed"] is True
        assert (
            arithmetic[
                "response_metadata"
            ]["usage"][
                "completion_tokens"
            ]
            == 2
        )
    finally:
        httpd.shutdown()

from __future__ import annotations

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
import json
from threading import Thread

from agent_runtime.baselines import (
    ArithmeticCapability,
)
from agent_runtime.language import (
    LanguageComposer,
    OpenAICompatibleBackend,
)
from agent_runtime.memory import AgentMemory
from agent_runtime.runtime import AgentRuntime


class Handler(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        length = int(
            self.headers["Content-Length"]
        )
        payload = json.loads(
            self.rfile.read(length)
        )
        Handler.seen.append(
            (self.path, payload)
        )
        systems = [
            msg["content"]
            for msg in payload["messages"]
            if msg["role"] == "system"
        ]
        content = "OK"
        if any(
            "arithmetic=14" in text
            for text in systems
        ):
            content = "The answer is 14."
        if any(
            "favorite=mango" in text
            for text in systems
        ):
            content += " I remember mango."
        body = json.dumps(
            {
                "id": "fake-1",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": content,
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
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


def server():
    Handler.seen.clear()
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        Handler,
    )
    thread = Thread(
        target=httpd.serve_forever,
        daemon=True,
    )
    thread.start()
    return (
        httpd,
        (
            "http://127.0.0.1:"
            f"{httpd.server_address[1]}"
        ),
    )


def test_openai_compatible_backend_and_capability_contribution():
    httpd, base = server()
    try:
        composer = LanguageComposer(
            OpenAICompatibleBackend(
                base_url=base,
                model="fake-model",
            )
        )
        runtime = AgentRuntime(
            composer=composer,
            contributors=[
                ArithmeticCapability()
            ],
        )
        response, trace = runtime.turn(
            "2 + 3 * 4"
        )
        assert response == "The answer is 14."
        path, payload = Handler.seen[-1]
        assert path == "/v1/chat/completions"
        assert payload["model"] == "fake-model"
        assert payload["stream"] is False
        assert any(
            "arithmetic=14" in msg["content"]
            for msg in payload["messages"]
        )
        composer_row = trace.executions[-1]
        assert (
            composer_row.capability
            == "language-composer"
        )
        assert composer_row.success is True
    finally:
        httpd.shutdown()


def test_semantic_memory_is_supplied_without_weight_update():
    httpd, base = server()
    try:
        memory = AgentMemory()
        memory.semantic["favorite"] = "mango"
        runtime = AgentRuntime(
            composer=LanguageComposer(
                OpenAICompatibleBackend(
                    base_url=base,
                    model="fake-model",
                )
            ),
            memory=memory,
        )
        response, _trace = runtime.turn(
            "what do I like?"
        )
        assert "remember mango" in response
        _path, payload = Handler.seen[-1]
        assert any(
            "favorite=mango" in msg["content"]
            for msg in payload["messages"]
            if msg["role"] == "system"
        )
    finally:
        httpd.shutdown()


def test_bad_backend_response_becomes_composer_failure_trace():
    class BadHandler(Handler):
        def do_POST(self):
            length = int(
                self.headers[
                    "Content-Length"
                ]
            )
            self.rfile.read(length)
            body = b'{"oops": true}'
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

    httpd = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        BadHandler,
    )
    thread = Thread(
        target=httpd.serve_forever,
        daemon=True,
    )
    thread.start()
    base = (
        "http://127.0.0.1:"
        f"{httpd.server_address[1]}"
    )
    try:
        runtime = AgentRuntime(
            composer=LanguageComposer(
                OpenAICompatibleBackend(
                    base_url=base,
                    model="bad",
                )
            )
        )
        response, trace = runtime.turn(
            "hello"
        )
        assert response == (
            "I could not compose a response."
        )
        row = trace.executions[-1]
        assert row.success is False
        assert (
            "invalid chat completion response"
            in row.error
        )
    finally:
        httpd.shutdown()



def test_zero_semantic_items_disables_direct_memory_dump():
    class CaptureBackend:
        name = "capture"

        def __init__(self):
            self.request = None

        def generate(self, req):
            from agent_runtime.language import (
                LanguageGeneration,
            )
            self.request = req
            return LanguageGeneration(
                text="ok"
            )

    backend = CaptureBackend()
    memory = AgentMemory()
    memory.semantic["favorite"] = "mango"
    runtime = AgentRuntime(
        composer=LanguageComposer(
            backend,
            max_semantic_items=0,
        ),
        memory=memory,
    )
    response, _trace = runtime.turn("hello")
    assert response == "ok"
    assert all(
        "favorite=mango"
        not in message.content
        for message in backend.request.messages
    )

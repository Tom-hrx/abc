from types import SimpleNamespace

from app.services.llm.client import LLMClient


def test_openai_call_disables_thinking():
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)

    client = LLMClient.__new__(LLMClient)
    client.config = SimpleNamespace(LLM_TEMPERATURE=0.2)
    client._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create),
        ),
    )

    client._openai_call(system="system", user="user", model="qwen3.8-max", max_tokens=128)

    assert captured["extra_body"] == {"enable_thinking": False}

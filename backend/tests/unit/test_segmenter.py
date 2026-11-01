from app.services.llm.client import LLMResult
from app.services.segmenter import run as segmenter


class ScriptedClient:
    """按顺序返回预设 JSON 的假客户端，用来验证续跑与偏移平移。"""

    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = 0

    def chat_json(self, **kwargs):
        data = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return LLMResult(
            data=data,
            raw="{}",
            model="scripted",
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=1,
        )


TEXT = "Hello world. Second sentence. Third one here."


def _payload(text, start, end, complete):
    return {
        "title": "T",
        "complete": complete,
        "paragraphs": [{"index": 1, "sentences": [{"index": 1, "text": text, "char_start": start, "char_end": end}]}],
    }


def test_continuation_rebases_offsets_and_renumbers():
    client = ScriptedClient([_payload("Hello world.", 0, 12, False), _payload("Second sentence.", 1, 17, True)])

    outcome = segmenter.run(client, TEXT, model="stub")

    assert outcome.status == "segmented"
    assert outcome.attempts == 2
    sentences = [s for p in outcome.paragraphs for s in p.sentences]
    assert [s.text for s in sentences] == ["Hello world.", "Second sentence."]
    # 第二段相对片段偏移 1，加上基准 12 应为 13
    assert (sentences[1].char_start, sentences[1].char_end) == (13, 29)
    assert TEXT[13:29] == "Second sentence."
    # 句子编号必须全局连续
    assert [s.index for s in sentences] == [1, 2]


def test_never_complete_is_incomplete():
    client = ScriptedClient([_payload("Hello world.", 0, 12, False)])
    outcome = segmenter.run(client, TEXT, model="stub", max_continuations=2)
    assert outcome.status == "incomplete"


def test_no_progress_stops_to_avoid_infinite_loop():
    # 偏移没有前进（char_end 停在基准点）：必须立即停止，不能刷调用
    payload = _payload("Hello world.", 0, 0, False)
    client = ScriptedClient([payload, payload, payload, payload])
    outcome = segmenter.run(client, TEXT, model="stub", max_continuations=5)
    assert outcome.status == "incomplete"
    assert client.calls == 1


def test_continuation_respects_max_attempts():
    payload = _payload("Hello world.", 0, 12, False)
    client = ScriptedClient([payload] * 6)
    outcome = segmenter.run(client, TEXT, model="stub", max_continuations=2)
    assert outcome.status == "incomplete"
    assert outcome.attempts == 3


def test_empty_output_is_incomplete():
    client = ScriptedClient([{"title": None, "complete": True, "paragraphs": []}])
    outcome = segmenter.run(client, TEXT, model="stub")
    assert outcome.status == "incomplete"
    assert outcome.paragraphs == []

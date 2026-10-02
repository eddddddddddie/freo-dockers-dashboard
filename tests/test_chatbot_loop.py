"""The answer loop's handling of odd API replies, with a fake client (no API calls)."""

from types import SimpleNamespace as NS

import chatbot as C


class FakeStream:
    def __init__(self, msg):
        self.msg = msg
        self.text_stream = iter([b.text for b in msg.content if b.type == "text"])

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


def fake_client(replies, sent):
    def stream(**kw):
        sent.append([m["role"] for m in kw["messages"]])
        return FakeStream(replies.pop(0))
    return NS(beta=NS(messages=NS(stream=stream)))


def msg(stop, *blocks):
    return NS(stop_reason=stop, content=list(blocks), usage=None)


def test_tool_use_with_no_tool_call_is_asked_again_not_sent_empty():
    """The API sometimes stops for "tool_use" with no content; the loop must ask
    again rather than send an empty tool-result turn (a 400 error)."""
    sent = []
    client = fake_client([msg("tool_use"), msg("end_turn", NS(type="text", text="Answer."))], sent)
    out = "".join(C.stream_answer(client, 2026, [{"role": "user", "content": "q"}]))
    assert out == "Answer." and sent == [["user"], ["user"]]


def test_repeated_empty_replies_give_a_plain_message():
    sent = []
    client = fake_client([msg("tool_use"), msg("tool_use"), msg("tool_use")], sent)
    out = "".join(C.stream_answer(client, 2026, [{"role": "user", "content": "q"}]))
    assert "ask again" in out and len(sent) == 3

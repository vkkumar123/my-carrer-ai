import asyncio

import pytest
from livekit.agents import llm

from interviewer.silence import drop_wait
from interviewer.turns import TurnPolicy, classify

# Real lines from a candidate's transcript, and what a real interviewer would treat them as.
TRANSCRIPT_LINES = {
    "Hmm": "filler",
    "Okay": "filler",
    "Yes": "filler",
    "Go": "filler",
    "I am writing it so once done I will show you the output.": "working",
    "I have written the query, you can check now.": "addressed",
    "It is showing me syntax error. Where it is?": "addressed",
    "Do you know Hindi?": "addressed",
    "kya ye sahi hai": "addressed",
    "So I will I will put it in on clause. And then we're": "statement",
    "Like customer data left joined with order data to identify the customer who didn't "
    "ordered anything.": "statement",
    "ek minute": "working",
    "So I have created the query, you can check it.": "addressed",
    "Can you share the feedback with me now?": "addressed",
    "let me think": "working",
    "I am done": "addressed",
    "I will create CTE": "statement",
}


@pytest.mark.parametrize(("text", "kind"), TRANSCRIPT_LINES.items())
def test_classifies_real_transcript_lines(text, kind):
    assert classify(text) == kind


def test_stays_quiet_while_candidate_works():
    p = TurnPolicy()
    p.note_workspace_activity(now=100)
    assert not p.should_reply("So I will create a CTE for the orders", now=110)
    assert not p.should_reply("Hmm", now=112)
    assert p.should_reply("I have written the query, you can check now.", now=115)


def test_saying_let_me_write_silences_until_they_come_back():
    p = TurnPolicy()
    assert not p.should_reply("Okay let me write it", now=0)
    assert not p.should_reply("So the join key is customer id", now=60)
    assert p.should_reply("Done, can you check?", now=90)
    assert p.should_reply("So the join key is customer id", now=95)  # no longer working


def test_short_answer_to_our_question_gets_a_reply():
    p = TurnPolicy()
    assert not p.should_reply("Okay", now=0)
    p.note_interviewer_said("Are you ready to start?", now=10)
    assert p.should_reply("Yes", now=15)
    assert not p.should_reply("Okay", now=60)  # long after the question: just a filler


def test_explanations_get_a_response_when_not_coding():
    p = TurnPolicy()
    assert p.should_reply("I would left join customers to orders and sum the amount", now=0)


def test_check_ins_are_rare_and_stop_if_unanswered():
    p = TurnPolicy()
    p.note_workspace_activity(now=0)
    assert p.should_check_in(now=60)
    assert not p.should_check_in(now=120)  # too soon while working
    assert p.should_check_in(now=400)
    assert not p.should_check_in(now=900)  # two unanswered check-ins: stop nagging
    p.should_reply("I'm still writing", now=950)
    assert p.should_check_in(now=1200)


def _chunk(text=None, tool=False, usage=False):
    delta = llm.ChoiceDelta(
        role="assistant",
        content=text,
        tool_calls=[llm.FunctionToolCall(name="get_hint", arguments="{}", call_id="c1")]
        if tool
        else [],
    )
    return llm.ChatChunk(
        id="x",
        delta=None if usage else delta,
        usage=llm.CompletionUsage(completion_tokens=1, prompt_tokens=1, total_tokens=2)
        if usage
        else None,
    )


async def _collect(chunks):
    async def gen():
        for c in chunks:
            yield c

    out = []
    async for c in drop_wait(gen()):
        out.append(c)
    return out


def _spoken(out):
    return "".join((c.delta.content or "") for c in out if c.delta is not None)


def test_wait_marker_is_silent_even_when_split():
    out = asyncio.run(_collect([_chunk("<wa"), _chunk("it>"), _chunk(usage=True)]))
    assert _spoken(out) == "" and any(c.usage for c in out)


def test_normal_reply_passes_through_unchanged():
    out = asyncio.run(_collect([_chunk("Ok"), _chunk("ay, walk me through it.")]))
    assert _spoken(out) == "Okay, walk me through it."


def test_reply_starting_like_marker_but_different_is_spoken():
    out = asyncio.run(_collect([_chunk("<"), _chunk("b>What")]))
    assert _spoken(out) == "<b>What"


def test_tool_calls_always_pass():
    out = asyncio.run(_collect([_chunk("<wait>"), _chunk(tool=True)]))
    assert any(c.delta and c.delta.tool_calls for c in out) and _spoken(out) == ""


def test_stray_marker_inside_speech_is_removed():
    out = asyncio.run(_collect([_chunk("Okay. "), _chunk("<wait> Go on.")]))
    assert _spoken(out) == "Okay.  Go on."

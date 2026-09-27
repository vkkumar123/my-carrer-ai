"""The configured voices must be valid for the Sarvam/Deepgram connectors (validated locally)."""

import pytest

from interviewer import main


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test")


@pytest.mark.parametrize("gender", ["female", "male"])
def test_sarvam_voices_are_valid(gender, monkeypatch):
    monkeypatch.setattr(main, "VOICE_PROVIDER", "sarvam")
    tts = main._make_tts(main.VOICES[gender])
    tts.update_options(target_language_code="hi-IN")  # switching to Hindi must be allowed
    stt = main._make_stt({"plan": {"questions": []}})
    assert stt is not None


@pytest.mark.parametrize("gender", ["female", "male"])
def test_deepgram_fallback_voices_are_valid(gender, monkeypatch):
    monkeypatch.setattr(main, "VOICE_PROVIDER", "deepgram")
    assert main._make_tts(main.VOICES[gender]) is not None
    assert main._make_stt({"plan": {"questions": [{"topic": "SQL"}]}}) is not None

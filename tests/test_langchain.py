"""Tests for the chat model wrapper (no network calls)."""

from types import SimpleNamespace

import pytest

from src.langchain import Langchain


class FakeProvider:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class FakeTemplate:
    def __init__(self, chain):
        self.chain = chain

    def __or__(self, model):
        return self.chain


class FakeChain:
    def __init__(self, chunks):
        self.chunks = chunks

    def stream(self, inputs):
        yield from self.chunks


def test_setup_providers(monkeypatch):
    for provider, env_key in [
        ("ollama", None),
        ("groq", "GROQ_API_KEY"),
        ("gemini", "GEMINI_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
    ]:
        monkeypatch.setattr(
            Langchain.os,
            "getenv",
            lambda key, env_key=env_key: "yes" if key == env_key else None,
        )
        monkeypatch.setattr(Langchain, "ChatOllama", FakeProvider)
        monkeypatch.setattr(Langchain, "ChatGroq", FakeProvider)
        monkeypatch.setattr(Langchain, "ChatGoogleGenerativeAI", FakeProvider)
        monkeypatch.setattr(Langchain, "ChatOpenAI", FakeProvider)

        client = Langchain(provider)

        assert isinstance(client.model, FakeProvider)


def test_setup_falls_back_to_ollama(monkeypatch):
    monkeypatch.setattr(Langchain.os, "getenv", lambda key: None)
    monkeypatch.setattr(Langchain, "ChatOllama", FakeProvider)

    client = Langchain("gemini")

    assert isinstance(client.model, FakeProvider)


def test_setup_handles_total_failure(monkeypatch):
    monkeypatch.setattr(Langchain.os, "getenv", lambda key: None)

    def fail(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(Langchain, "ChatOllama", fail)
    monkeypatch.setattr(Langchain, "ChatGoogleGenerativeAI", fail)
    monkeypatch.setattr(Langchain, "ChatOpenAI", fail)
    monkeypatch.setattr(Langchain, "ChatGroq", fail)

    client = Langchain("gemini")

    assert client.model is None


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("text", "text"),
        (["a", {"text": "b"}, 3], "ab3"),
        ({"text": "mapping"}, "{'text': 'mapping'}"),
    ],
)
def test_content_to_text(content, expected):
    assert Langchain._content_to_text(content) == expected


def test_stream_yields_content_and_records_history(monkeypatch):
    client = object.__new__(Langchain)
    client.name = "Fred"
    client.model = object()
    client._history = []
    client._MAX_HISTORY = 6
    chunks = [
        SimpleNamespace(content="Hello "),
        SimpleNamespace(content=[{"text": "world"}, "!"]),
    ]
    monkeypatch.setattr(
        client, "_template", lambda: FakeTemplate(FakeChain(chunks))
    )

    assert list(client.stream("hi")) == ["Hello ", "world!"]
    assert len(client._history) == 2


def test_stream_reports_provider_error_and_keeps_partial(monkeypatch):
    client = object.__new__(Langchain)
    client.name = "Fred"
    client.model = object()
    client._history = []
    client._MAX_HISTORY = 6

    class BrokenChain(FakeChain):
        def stream(self, inputs):
            yield SimpleNamespace(content="partial")
            raise RuntimeError("boom")

    monkeypatch.setattr(
        client, "_template", lambda: FakeTemplate(BrokenChain([]))
    )

    chunks = list(client.stream("hi"))

    assert chunks[0] == "partial"
    assert "Core Error" in chunks[-1]
    assert client._history[-1].content == "partial"


def test_stream_uses_mock_without_model(monkeypatch):
    client = object.__new__(Langchain)
    client.name = "Fred"
    client.model = None
    client._history = []
    client._MAX_HISTORY = 6
    monkeypatch.setattr(Langchain, "_mock", lambda: iter(["offline"]))

    assert list(client.stream("")) == ["offline"]
    assert list(client.stream("hello")) == ["offline"]


def test_respond_prints_stream(monkeypatch, capsys):
    client = object.__new__(Langchain)
    monkeypatch.setattr(client, "stream", lambda user_input: iter(["a", "b"]))

    client.respond("hi")

    assert capsys.readouterr().out == "ab"
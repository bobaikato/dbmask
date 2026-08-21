"""Regression tests for LLM configuration plumbing and data-egress controls.

Two bugs and one missing control:

* ``LocalProvider`` supported ``api_style="openai"`` (LM Studio, vLLM, any
  OpenAI-compatible local server) but ``LLMConfig`` had no such field and the
  factory never passed it — so YAML users literally could not select it.
* Nothing told the operator that enabling the OpenAI provider sends sampled
  column values off the machine.
* There was no way to use an LLM without sending values at all. New
  ``llm.send_values: false`` sends the column name only.
"""
from __future__ import annotations

from typing import Sequence

import pytest

from dbmask.cli import cli
from dbmask.config import Config, LLMConfig
from dbmask.detection.pipeline import DetectionPipeline
from dbmask.llm.base import LLMProvider, LLMResult
from dbmask.llm.factory import create_provider


# -- api_style plumbing --------------------------------------------------------

def test_factory_passes_api_style_to_local_provider():
    pytest.importorskip("requests")
    cfg = LLMConfig(enabled=True, provider="local", model="m",
                    base_url="http://localhost:1234", api_style="openai")
    provider = create_provider(cfg)
    assert provider is not None
    assert provider.api_style == "openai"


def test_factory_defaults_local_to_ollama_style():
    pytest.importorskip("requests")
    provider = create_provider(LLMConfig(enabled=True, provider="local"))
    assert provider is not None
    assert provider.api_style == "ollama"


def test_factory_rejects_unknown_api_style():
    pytest.importorskip("requests")
    with pytest.raises(ValueError, match="api_style"):
        create_provider(LLMConfig(enabled=True, provider="local", api_style="grpc"))


def test_disabled_returns_none():
    assert create_provider(LLMConfig(enabled=False)) is None


# -- metadata-only mode --------------------------------------------------------

class RecordingProvider(LLMProvider):
    def __init__(self):
        self.calls: list[tuple[str, list[str]]] = []

    def classify(self, column_name: str, sample: Sequence[str]) -> LLMResult:
        self.calls.append((column_name, list(sample)))
        return LLMResult(sensitive=True, rule="email", confidence=0.9, token_usage=1)


class StubConnector:
    name = "stub"

    def __init__(self, values):
        self._values = values

    def sample_values(self, schema, table, column, limit=100):
        return self._values[:limit]


def _pipeline(send_values: bool):
    config = Config()
    config.llm.enabled = True
    config.llm.send_values = send_values
    config.llm.sample_size = 3
    provider = RecordingProvider()
    return DetectionPipeline(config=config, llm=provider), provider


# Values that no built-in pattern recognizes, so the pipeline falls through
# to the LLM layer.
_UNPATTERNED = [
    "order notes alpha",
    "order notes beta",
    "order notes gamma",
    "order notes delta",
    "order notes epsilon",
]


def test_send_values_true_sends_trimmed_sample():
    pipeline, provider = _pipeline(send_values=True)
    pipeline.analyze_column(StubConnector(_UNPATTERNED), "s", "t", "contact")
    assert provider.calls == [("contact", _UNPATTERNED[:3])]


def test_send_values_false_sends_no_values():
    pipeline, provider = _pipeline(send_values=False)
    pipeline.analyze_column(StubConnector(_UNPATTERNED), "s", "t", "contact")
    (column, sample), = provider.calls
    assert column == "contact"
    assert sample == []


def test_prompt_without_values_explains_metadata_only():
    prompt = LLMProvider.build_prompt("email", [])
    assert "no values provided" in prompt
    assert "column name alone" in prompt
    assert "email" in prompt


def test_prompt_with_values_lists_them():
    prompt = LLMProvider.build_prompt("email", ["a@x.io"])
    assert "- a@x.io" in prompt


# -- CLI egress warning --------------------------------------------------------

def test_cli_warns_before_sending_values_to_openai(cli_env):
    cfg = cli_env.make_config(
        llm={"enabled": True, "provider": "openai", "api_key": "sk-test"}
    )
    result = cli_env.runner.invoke(cli, ["scan", "--config", cfg])
    # The warning must be printed regardless of whether the provider can
    # actually be constructed in this environment (the openai package may be
    # missing) — it fires before any network client is built.
    assert "will be sent to" in result.output
    assert "api.openai.com" in result.output


def test_cli_metadata_only_warning_mentions_no_values(cli_env):
    cfg = cli_env.make_config(
        llm={"enabled": True, "provider": "openai", "api_key": "sk-test",
             "send_values": False}
    )
    result = cli_env.runner.invoke(cli, ["scan", "--config", cfg])
    assert "metadata-only" in result.output


def test_cli_local_provider_no_egress_warning(cli_env):
    cfg = cli_env.make_config(llm={"enabled": False})
    result = cli_env.runner.invoke(cli, ["scan", "--config", cfg])
    assert "will be sent to" not in result.output

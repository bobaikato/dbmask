"""Regression tests: masking fails closed when the scan is incomplete.

The bug: ``Runner.mask()`` called ``self.scan().decisions`` and threw the
report's ``errors`` away. A column whose analysis raised (permissions, weird
types, transient DB errors) simply got no decision — so it was silently left
unmasked while the command exited 0. A privacy tool must treat "I could not
check this column" as a reason to stop, not as a pass.

Now: ``Runner.mask()`` raises ``ScanIncompleteError`` unless the caller opts
in with ``allow_partial=True``; the CLI mirrors this with ``--allow-partial``
and non-zero exit codes.
"""
from __future__ import annotations

import pytest

from dbmask.cli import cli
from dbmask.connectors.sql import SQLConnector
from dbmask.runner import Runner, ScanIncompleteError


@pytest.fixture()
def broken_email_column(monkeypatch):
    """Make analysis of the ``email`` column blow up, as a flaky DB would."""
    original = SQLConnector.sample_values

    def failing(self, schema, table, column, limit=100):
        if column == "email":
            raise RuntimeError("simulated failure reading column")
        return original(self, schema, table, column, limit)

    monkeypatch.setattr(SQLConnector, "sample_values", failing)


def _runner_config(cli_env):
    from dbmask.config import Config

    return Config.load(cli_env.make_config(masking={"dry_run": False}))


# -- library level -------------------------------------------------------------

def test_mask_raises_on_incomplete_scan(cli_env, broken_email_column):
    with Runner(_runner_config(cli_env)) as runner:
        with pytest.raises(ScanIncompleteError, match="could not be analyzed"):
            runner.mask()
    assert "mary.johnson@example.com" in cli_env.read("email")


def test_mask_allow_partial_opts_in_explicitly(cli_env, broken_email_column):
    with Runner(_runner_config(cli_env)) as runner:
        results = runner.mask(allow_partial=True)
    assert results  # other columns (full_name) still masked
    # The failing column is untouched -- but that now happened by explicit choice.
    assert "mary.johnson@example.com" in cli_env.read("email")
    assert "Mary Johnson" not in cli_env.read("full_name")


def test_mask_with_explicit_decisions_is_unaffected(cli_env):
    """Callers who pass their own decisions keep full control."""
    with Runner(_runner_config(cli_env)) as runner:
        report = runner.scan()
        assert not report.errors
        results = runner.mask(report.decisions)
    assert results


# -- CLI level -----------------------------------------------------------------

def test_cli_mask_aborts_on_scan_errors(cli_env, broken_email_column):
    cfg = cli_env.make_config()
    result = cli_env.runner.invoke(cli, ["mask", "--config", cfg, "--apply"])
    assert result.exit_code == 2
    assert "Aborting" in result.output
    assert "--allow-partial" in result.output
    # Nothing was written -- not even the columns that scanned cleanly.
    assert "Mary Johnson" in cli_env.read("full_name")
    assert "mary.johnson@example.com" in cli_env.read("email")


def test_cli_mask_allow_partial_proceeds_with_warning(cli_env, broken_email_column):
    cfg = cli_env.make_config()
    result = cli_env.runner.invoke(
        cli, ["mask", "--config", cfg, "--apply", "--allow-partial"]
    )
    assert result.exit_code == 0, result.output
    assert "[error] scan:" in result.output
    assert "Mary Johnson" not in cli_env.read("full_name")   # masked
    assert "mary.johnson@example.com" in cli_env.read("email")  # skipped, loudly


def test_cli_scan_exits_nonzero_on_errors(cli_env, broken_email_column):
    cfg = cli_env.make_config()
    result = cli_env.runner.invoke(cli, ["scan", "--config", cfg])
    assert result.exit_code == 3
    assert "Scan incomplete" in result.output

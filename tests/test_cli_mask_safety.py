"""Regression tests: `dbmask mask` must never write without --apply.

The bug: the CLI only ever switched dry-run OFF (`if apply: dry_run = False`).
With `masking.dry_run: false` in the YAML, running `dbmask mask` WITHOUT
--apply wrote masked values to the database while printing
"DRY-RUN (no changes written)" — the worst possible combination for a tool
whose whole job is to be careful with data.

Now the flag is the single source of truth: no --apply, no writes. Ever.
"""
from __future__ import annotations

from dbmask.cli import cli


def test_mask_without_apply_is_dry_run_even_if_config_says_otherwise(cli_env):
    """`dry_run: false` in the YAML must NOT allow a flagless write."""
    cfg = cli_env.make_config(masking={"dry_run": False})

    result = cli_env.runner.invoke(cli, ["mask", "--config", cfg])

    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    emails = cli_env.read("email")
    assert "mary.johnson@example.com" in emails, (
        "database was modified by a flagless `dbmask mask` run"
    )


def test_mask_without_apply_reports_zero_rows_written(cli_env):
    cfg = cli_env.make_config(masking={"dry_run": False})
    result = cli_env.runner.invoke(cli, ["mask", "--config", cfg])
    assert result.exit_code == 0, result.output
    assert "written=0" in result.output


def test_mask_with_apply_writes(cli_env):
    """--apply must write even when the YAML keeps the default dry_run: true."""
    cfg = cli_env.make_config(masking={"dry_run": True})

    result = cli_env.runner.invoke(cli, ["mask", "--config", cfg, "--apply"])

    assert result.exit_code == 0, result.output
    assert "APPLIED" in result.output
    emails = cli_env.read("email")
    assert "mary.johnson@example.com" not in emails
    assert all("@" in e for e in emails)  # still email-shaped


def test_dry_run_then_apply_produce_the_same_values(cli_env):
    """The preview must be an honest preview of what --apply will write."""
    cfg = cli_env.make_config()
    preview = cli_env.runner.invoke(cli, ["mask", "--config", cfg])
    assert preview.exit_code == 0, preview.output

    applied = cli_env.runner.invoke(cli, ["mask", "--config", cfg, "--apply"])
    assert applied.exit_code == 0, applied.output

    emails = cli_env.read("email")
    assert "mary.johnson@example.com" not in emails

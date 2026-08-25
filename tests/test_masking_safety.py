"""Regression tests for three masking-safety holes.

1. **Primary-key columns silently skipped.** ``update_rows`` (correctly)
   never rewrites key columns — but the engine still planned them, showed
   them masked in the preview, and said nothing. Now they are excluded up
   front, reported in ``TableMaskResult.skipped_columns``, and the CLI warns
   loudly that the column still holds its original data.

2. **Dry runs wrote to the seed map.** A "no changes" preview persisted
   (original -> masked) pairs as a side effect. Dry runs are now read-only
   towards the seed map; determinism keeps the preview identical to what a
   later --apply writes.

3. **Previews printed original PII to the terminal.** ``dbmask mask``'s
   before/after sample put real values into scrollback and CI logs. Originals
   are now redacted shape-only by default; ``--show-values`` opts in.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from dbmask.cli import cli
from dbmask.config import DatabaseConfig, MaskingConfig, SeedMapConfig
from dbmask.connectors.sql import SQLConnector
from dbmask.detection.result import Decision, Sensitivity
from dbmask.masking.engine import ColumnPlan, MaskingEngine


def _decision(table: str, column: str, rule: str = "email") -> Decision:
    return Decision(
        database="t", schema="main", table=table, column=column,
        sensitivity=Sensitivity.SENSITIVE, rule=rule,
        source="pattern", confidence=1.0,
    )


# -- 1. primary-key columns ----------------------------------------------------

def _pk_db(tmp_path: Path) -> Path:
    db = tmp_path / "pk.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE accounts (
            email TEXT PRIMARY KEY,     -- sensitive AND the key
            holder TEXT
        );
        INSERT INTO accounts VALUES
            ('mary@example.com', 'Mary Johnson'),
            ('bob@example.com', 'Robert Smith');
        """
    )
    conn.commit()
    conn.close()
    return db


def test_sensitive_pk_column_is_reported_not_silently_dropped(tmp_path):
    db = _pk_db(tmp_path)
    engine = MaskingEngine(
        MaskingConfig(dry_run=False, seed="s", seed_map=SeedMapConfig(enabled=False))
    )
    with SQLConnector(DatabaseConfig(url=f"sqlite:///{db}", name="t")) as connector:
        result = engine.mask_table(
            connector, "main", "accounts",
            [_decision("accounts", "email"), _decision("accounts", "holder", "full_name")],
        )

    assert [p.column for p in result.skipped_columns] == ["email"]
    assert [p.column for p in result.columns] == ["holder"]
    # The preview must not pretend the key column was masked.
    for sample in result.preview:
        assert "email" not in sample["before"]

    conn = sqlite3.connect(db)
    emails = [r[0] for r in conn.execute("SELECT email FROM accounts")]
    holders = [r[0] for r in conn.execute("SELECT holder FROM accounts")]
    conn.close()
    assert set(emails) == {"mary@example.com", "bob@example.com"}  # untouched
    assert "Mary Johnson" not in holders  # non-key column masked


def test_only_pk_sensitive_masks_nothing_but_says_so(tmp_path):
    db = _pk_db(tmp_path)
    engine = MaskingEngine(
        MaskingConfig(dry_run=False, seed="s", seed_map=SeedMapConfig(enabled=False))
    )
    with SQLConnector(DatabaseConfig(url=f"sqlite:///{db}", name="t")) as connector:
        result = engine.mask_table(
            connector, "main", "accounts", [_decision("accounts", "email")]
        )
    assert result.skipped_columns and not result.columns
    assert result.rows_written == 0


def test_cli_warns_about_unmaskable_pk_column(cli_env):
    conn = sqlite3.connect(cli_env.db)
    conn.executescript(
        """
        CREATE TABLE subscribers (email TEXT PRIMARY KEY, note TEXT);
        INSERT INTO subscribers VALUES ('a.person@example.com', 'x1'),
                                       ('b.person@example.com', 'x2');
        """
    )
    conn.commit()
    conn.close()

    result = cli_env.runner.invoke(
        cli, ["mask", "--config", cli_env.make_config(), "--apply"]
    )
    assert result.exit_code == 0, result.output
    assert "NOT MASKED" in result.output
    assert "primary-key" in result.output
    assert "a.person@example.com" in cli_env.read("email", "subscribers")


# -- 2. dry runs must not write the seed map -----------------------------------

def test_dry_run_records_no_seed_pairs(tmp_path):
    url = f"sqlite:///{tmp_path / 'seeds.db'}"
    plan = ColumnPlan(schema="main", table="t", column="company",
                      rule="city", strategy_name="fake_city")

    dry = MaskingEngine(MaskingConfig(dry_run=True, seed="s",
                                      seed_map=SeedMapConfig(enabled=True, url=url)))
    previewed = dry.mask_value("Tesla", plan)
    store = dry.seed_store()
    assert store is not None and store.count() == 0
    dry.close()

    # And the eventual apply writes exactly what the preview showed.
    wet = MaskingEngine(MaskingConfig(dry_run=False, seed="s",
                                      seed_map=SeedMapConfig(enabled=True, url=url)))
    applied = wet.mask_value("Tesla", plan)
    assert applied == previewed
    store = wet.seed_store()
    assert store is not None and store.count() == 1
    wet.close()


def test_dry_run_still_reads_existing_pairs(tmp_path):
    """Pairs recorded by a previous apply must drive the preview."""
    url = f"sqlite:///{tmp_path / 'seeds.db'}"
    plan = ColumnPlan(schema="main", table="t", column="company",
                      rule="city", strategy_name="fake_city")

    wet = MaskingEngine(MaskingConfig(dry_run=False, seed="s",
                                      seed_map=SeedMapConfig(enabled=True, url=url)))
    recorded = wet.mask_value("Tesla", plan)
    wet.close()

    dry = MaskingEngine(MaskingConfig(dry_run=True, seed="another-seed",
                                      seed_map=SeedMapConfig(enabled=True, url=url)))
    assert dry.mask_value("Tesla", plan) == recorded  # pair wins over recompute
    dry.close()


# -- 3. preview redaction ------------------------------------------------------

def test_preview_redacts_originals_by_default(cli_env):
    result = cli_env.runner.invoke(cli, ["mask", "--config", cli_env.make_config()])
    assert result.exit_code == 0, result.output
    assert "mary.johnson@example.com" not in result.output
    assert "Mary Johnson" not in result.output
    assert "****.*******@*******.***" in result.output  # shape preserved
    assert "--show-values" in result.output


def test_preview_shows_originals_only_on_request(cli_env):
    result = cli_env.runner.invoke(
        cli, ["mask", "--config", cli_env.make_config(), "--show-values"]
    )
    assert result.exit_code == 0, result.output
    assert "mary.johnson@example.com" in result.output


# -- bonus: default-seed warning ----------------------------------------------

def test_default_public_seed_triggers_warning(cli_env):
    cfg = cli_env.make_config(masking={"seed": "dbmask"})
    result = cli_env.runner.invoke(cli, ["mask", "--config", cfg])
    assert "publicly-known default" in result.output


def test_custom_seed_no_warning(cli_env):
    result = cli_env.runner.invoke(cli, ["mask", "--config", cli_env.make_config()])
    assert "publicly-known default" not in result.output

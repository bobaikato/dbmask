"""Create a disposable PostgreSQL source/target pair for Ota pressure testing."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

DDL = """
DROP TABLE IF EXISTS customers;
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    account_status TEXT NOT NULL
);
INSERT INTO customers (id, full_name, email, account_status) VALUES
    (1, 'Avery Stone', 'avery.stone@example.test', 'active'),
    (2, 'Jordan Reed', 'jordan.reed@example.test', 'active'),
    (3, 'Morgan Vale', 'morgan.vale@example.test', 'inactive');
"""


def require_disposable_database(url: str, expected_database: str) -> URL:
    parsed = make_url(url)
    if parsed.drivername != "postgresql+psycopg2":
        raise ValueError("the PostgreSQL pressure fixture requires postgresql+psycopg2")
    if parsed.host != "localhost" or parsed.port != 5432:
        raise ValueError("the PostgreSQL pressure fixture requires localhost:5432")
    if parsed.username != "dbmask" or parsed.password != "dbmask-pressure-only":
        raise ValueError("the PostgreSQL pressure fixture requires its synthetic service account")
    if parsed.database != expected_database:
        raise ValueError(f"expected disposable database {expected_database!r}")
    if parsed.query:
        raise ValueError("the PostgreSQL pressure fixture does not accept URL query parameters")
    return parsed


def recreate_database(url: URL, database: str) -> None:
    admin_url = url.set(database="postgres")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{database}"'))


def seed(url: URL) -> None:
    engine = create_engine(url)
    with engine.begin() as connection:
        for statement in DDL.split(";"):
            if statement.strip():
                connection.execute(text(statement))


def main() -> None:
    source = require_disposable_database(os.environ["DBMASK_SOURCE_URL"], "dbmask_source")
    target = require_disposable_database(os.environ["DBMASK_TARGET_URL"], "dbmask_target")
    recreate_database(source, "dbmask_source")
    recreate_database(target, "dbmask_target")
    seed(source)
    seed(target)


if __name__ == "__main__":
    main()

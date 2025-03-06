import pytest

from sqlalchemy_utils import create_database, drop_database
from sqlalchemy import text

import migrate.systemdata
import nccrd.db
from nccrd.config import nccrd_config
from test import TestSession
from test.factories import FactorySession


@pytest.fixture(scope='session', autouse=True)
def database():
    """An auto-use, run-once fixture that provides a clean
    database with an up-to-date ODP schema."""
    create_database(url := nccrd_config.NCCRD.DB.URL)
    try:
        migrate.systemdata.init_database_schema()
        yield
    finally:
        drop_database(url)


@pytest.fixture(autouse=True)
def session():
    """An auto-use, per-test fixture that disposes of the current
    session after every test."""
    try:
        yield
    finally:
        nccrd.db.Session.remove()
        FactorySession.remove()
        TestSession.remove()


@pytest.fixture(autouse=True)
def delete_all_data():
    """An auto-use, per-test fixture that deletes all table data
    after every test."""
    try:
        yield
    finally:
        with nccrd.db.engine.begin() as conn:
            for table in nccrd.db.Base.metadata.tables:
                conn.execute(text(f'ALTER TABLE {table} DISABLE TRIGGER ALL'))
                conn.execute(text(f'DELETE FROM {table}'))
                conn.execute(text(f'ALTER TABLE {table} ENABLE TRIGGER ALL'))

import logging
import os
import pathlib
from dotenv import load_dotenv
from sqlalchemy import text, event, DDL
from sqlalchemy.exc import ProgrammingError
from nccrd.db.models import Adaptaion,Mitigation,Submission, Trees, Vocabulary, VocabularyXrefVocabulary, VocabularyXrefTree

from nccrd.db import Base, engine

logger = logging.getLogger(__name__)


def initialize():
    logger.info('Initializing static system data...')

    load_dotenv(pathlib.Path(os.getcwd()) / '.env')  # for a local run; in a container there's no .env

    init_database_schema()

    logger.info('Done.')


def init_database_schema():
    """Create or update the ODP database schema."""
    cwd = os.getcwd()
    os.chdir(pathlib.Path(__file__).parent)

    event.listen(Base.metadata, 'before_create', DDL("CREATE SCHEMA IF NOT EXISTS nccrd"))

    try:
        # alembic_cfg = Config('alembic.ini')
        try:
            with engine.connect() as conn:
                conn.execute(text('select version_num from alembic_version'))
            schema_exists = True
        except ProgrammingError:  # from psycopg2.errors.UndefinedTable
            schema_exists = False

        if not schema_exists:
            Base.metadata.create_all(engine)
            # command.stamp(alembic_cfg, 'head')
            logger.info('Created the database schema.')
        
        create_static_system_data(Base.metadata, engine.connect())
        # This will trigger the creation of static system data
        
    except Exception as e:
        logger.error(f'Error initializing database schema: {e}')
        raise   
    finally:
        os.chdir(cwd)

#Create the static system data
# @event.listens_for(Base.metadata, 'after_create')
def create_static_system_data(target, connection, **kw):
    """Create static system data."""
    logger.info('Creating static system data...')

    import pandas as pd
    import geopandas as gpd
    # Submission.create_default_submissions()

    # # Create default adaptation and mitigation entries
    # Adaptaion.create_default_adaptations()
    # Mitigation.create_default_mitigations()

    logger.info('Static system data created.')

if __name__ == '__main__':
    print("Started ")
    initialize()
    print("Finished ")
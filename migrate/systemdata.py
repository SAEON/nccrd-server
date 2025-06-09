import logging
import os
import pathlib

from dotenv import load_dotenv
from sqlalchemy import text, event, DDL
from sqlalchemy.exc import ProgrammingError
from nccrd.db.models import Adaptaion,Mitigation,Submission

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
    import os
    from shapely import wkt
    from nccrd.db.models.region import Province, District, LocalDistrict, Country

    print(os.getcwd())
    print(os.listdir(os.getcwd()))
    print("Current working directory:", os.getcwd())
    print("Creating static system data...")
    pd.read_csv(
        './region_data/provinces.csv',
        dtype={
            'PR_MDB_C': str,
            'PR_CODE': int,
            'PR_CODE_st': int,
            'PR_NAME': str,
            'ALBERS_ARE': float,
            'SHAPE_Leng': float,
            'X': float,
            'Y': float,
            'Shape__Area': float,
            'Shape__Length': float
        }
    ).to_sql(
        'province',
        con=connection,
        schema='nccrd',
        if_exists='replace',
        index=False
    )
    logger.info('Provinces data loaded.')

    # Load Districts data
    gdf_district = gpd.read_file('./region_data/DistrictMunicipality2018.json')
    gdf_district["geometry"] = gdf_district["geometry"].apply(lambda geom: geom.wkt)
    gdf_district.to_sql('district', con=connection, schema='nccrd', if_exists='replace', index=False)

    logger.info("District data loaded.")

    # Load Local Districts data
    gdf_local_district = gpd.read_file('./region_data/LocalMunicipality2018.json')
    gdf_local_district["geometry"] = gdf_local_district["geometry"].apply(lambda geom: geom.wkt)
    gdf_local_district.to_sql('local_district', con=connection, schema='nccrd', if_exists='replace', index=False)

    logger.info("Local District data loaded.")

    # Load Country data
    gdf_country = gpd.read_file('./region_data/south_africa_South_Africa_Country_Boundary.geojson')
    gdf_country["geometry"] = gdf_country["geometry"].apply(lambda geom: geom.wkt)
    gdf_country.to_sql('country', con=connection, schema='nccrd', if_exists='replace', index=False)
        #
    # Create default submissions
    # Submission.create_default_submissions()

    # # Create default adaptation and mitigation entries
    # Adaptaion.create_default_adaptations()
    # Mitigation.create_default_mitigations()

    logger.info('Static system data created.')

if __name__ == '__main__':
    print("Started ")
    initialize()
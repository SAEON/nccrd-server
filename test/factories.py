from random import randint, choice

import factory
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker
from sqlalchemy.orm import scoped_session, sessionmaker

import nccrd.db

FactorySession = scoped_session(sessionmaker(
    bind=nccrd.db.engine,
    autocommit=False,
    autoflush=False,
    future=True,
))

fake = Faker()


class NCCRDModelFactory(SQLAlchemyModelFactory):
    class Meta:
        sqlalchemy_session = FactorySession
        sqlalchemy_session_persistence = 'commit'

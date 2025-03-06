from sqlalchemy.orm import scoped_session, sessionmaker

import nccrd.db

# SQLAlchemy session to use for making assertions about database state
TestSession = scoped_session(sessionmaker(
    bind=nccrd.db.engine,
    autocommit=False,
    autoflush=False,
    future=True
))

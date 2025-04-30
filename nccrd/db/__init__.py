from fileinput import close
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from nccrd.config import nccrd_config


engine = create_engine(
    nccrd_config.NCCRD.DB.URL,
    echo=nccrd_config.NCCRD.DB.ECHO,
    isolation_level=nccrd_config.NCCRD.DB.ISOLATION_LEVEL,
    future=True,
)

Session = scoped_session(
    sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        future=True,
    )
)


def get_db():
    db = Session()
    try:
        yield  db
    finally:
        close()

class _Base:
    __table_args__ = {"schema": "nccrd"}

    def save(self):
        Session.add(self)
        Session.flush()

    def delete(self):
        Session.delete(self)
        Session.flush()

    def __repr__(self):
        try:
            params = ', '.join(f'{attr}={getattr(self, attr)!r}' for attr in getattr(self, '_repr_'))
            return f'{self.__class__.__name__}({params})'
        except AttributeError:
            return object.__repr__(self)


Base = declarative_base(cls=_Base)

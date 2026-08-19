from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from nccrd.config import nccrd_config


engine = create_engine(
    nccrd_config.NCCRD.DB.URL,
    echo=nccrd_config.NCCRD.DB.ECHO,
    isolation_level=nccrd_config.NCCRD.DB.ISOLATION_LEVEL,
    future=True,
)

_session_factory = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)

# Retained for the test suite's cross-test cleanup pattern (Session.remove()
# in test/conftest.py). Request-handling code must NOT use this directly —
# see get_db() below. Sharing one thread-local scoped_session across
# concurrent FastAPI requests trips "This session is provisioning a new
# connection; concurrent operations are not permitted" under load, since
# worker-thread reuse can alias two in-flight requests onto the same
# thread-local key.
Session = scoped_session(_session_factory)


def get_db():
    """Yield a session that's independent per request (not shared via
    thread-local state) and reliably closed when the request ends —
    including on error, via FastAPI's dependency teardown."""
    db = _session_factory()
    try:
        yield db
    finally:
        db.close()

class _Base:
    __table_args__ = {"schema": "nccrd"}

    def __repr__(self):
        try:
            params = ', '.join(f'{attr}={getattr(self, attr)!r}' for attr in getattr(self, '_repr_'))
            return f'{self.__class__.__name__}({params})'
        except AttributeError:
            return object.__repr__(self)


Base = declarative_base(cls=_Base)

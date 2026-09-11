from __future__ import annotations

from typing import Dict, Type

from pydantic import BaseSettings


class BaseConfig(BaseSettings):
    """Base configuration class.

    This provides lazy loading of environment variable subgroups,
    allowing us to reference sub-configurations in an intuitive way
    and without having to either optionalize all attributes of a sub-
    configuration or force them to appear in the environment of
    services that don't require them.

    The `_subconfig` mapping is used to define the set of sub-
    configurations that are available on a 'parent' config class.
    The keys become attributes on the parent config instance; the
    values indicate the corresponding sub-config classes, which are
    instantiated (and their settings read from the environment and
    validated) upon first access.

    Note: while sub-configurations and their values are dereferenced
    in code using the usual dot-notation, the corresponding environment
    variables - and hence the `env_prefix`s - should use underscores
    in place of dots, so that environment variables may be used in
    shell commands/scripts.
    """

    _subconfig: Dict[str, Type[BaseConfig] | BaseConfig] = {}

    def __getattr__(self, name) -> BaseConfig:
        if name in self._subconfig:
            if not isinstance(self._subconfig[name], BaseConfig):
                self._subconfig[name] = (self._subconfig[name])()
            return self._subconfig[name]

        raise AttributeError

    class Config:
        env_file = '.env'


class DBConfigMixin(BaseSettings):
    HOST: str
    PORT: int = 5432
    NAME: str
    USER: str
    PASS: str
    ECHO: bool = False  # when True, SQLAlchemy emits SQL commands to stderr
    ISOLATION_LEVEL: str = 'READ COMMITTED'  # read committed is the PG default

    @property
    def URL(self) -> str:
        return f'postgresql://{self.USER}:{self.PASS}@{self.HOST}:{self.PORT}/{self.NAME}'


class NCCRDDBConfig(BaseConfig, DBConfigMixin):
    class Config:
        env_prefix = 'NCCRD_DB_'


class NCCRDInnerConfig(BaseConfig):
    class Config:
        env_prefix = 'NCCRD_'

    API_URL: str = None
    JWT_SECRET: str
    JWT_ALGORITHM: str = 'HS256'
    JWT_EXPIRES_MINUTES: int = 480
    # Comma-separated list of allowed frontend origins for CORS, e.g.
    # "http://192.168.1.50:5024,https://nccrd.saeon.ac.za". Deliberately a
    # plain string (not a pydantic List field) — env vars are simplest to
    # write as comma-separated text, split in nccrd/api/__init__.py.
    CORS_ORIGINS: str = (
        'http://nccrd.localhost:2021,'
        'http://localhost:5024,http://127.0.0.1:5024,'
        'http://localhost:5173,http://127.0.0.1:5173,'
        'http://localhost:5174,http://127.0.0.1:5174,'
        'http://localhost:5175'
    )

    _subconfig = {
        'DB': NCCRDDBConfig,
    }


class NCCRDRootConfig(BaseConfig):
    class Config:
        env_prefix = ''

    _subconfig = {
        'NCCRD': NCCRDInnerConfig,
    }


nccrd_config = NCCRDRootConfig()

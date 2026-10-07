from __future__ import annotations

from typing import ClassVar, Dict, Optional, Type, Union

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Every settings group reads the same .env, which holds every group's variables
#: (NCCRD_DB_*, NCCRD_*...): each ignores the ones it doesn't declare, which
#: pydantic-settings 2 would otherwise reject. Repeated in each class below
#: because pydantic merges config base by base: NCCRDDBConfig's second base,
#: DBConfigMixin, would otherwise reset these to the defaults.
_SHARED = dict(env_file='.env', extra='ignore')


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

    # A ClassVar, not a pydantic private attribute: those are themselves looked
    # up through __getattr__, which would recurse here.
    _subconfig: ClassVar[Dict[str, Union[Type[BaseConfig], BaseConfig]]] = {}

    def __getattr__(self, name) -> BaseConfig:
        subconfig = type(self)._subconfig
        if name in subconfig:
            if not isinstance(subconfig[name], BaseConfig):
                subconfig[name] = subconfig[name]()
            return subconfig[name]
        return super().__getattr__(name)

    model_config = SettingsConfigDict(**_SHARED)


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
    model_config = SettingsConfigDict(**_SHARED, env_prefix='NCCRD_DB_')


class NCCRDInnerConfig(BaseConfig):
    model_config = SettingsConfigDict(**_SHARED, env_prefix='NCCRD_')

    API_URL: Optional[str] = None
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

    _subconfig: ClassVar[Dict[str, Union[Type[BaseConfig], BaseConfig]]] = {
        'DB': NCCRDDBConfig,
    }


class NCCRDRootConfig(BaseConfig):
    model_config = SettingsConfigDict(**_SHARED, env_prefix='')

    _subconfig: ClassVar[Dict[str, Union[Type[BaseConfig], BaseConfig]]] = {
        'NCCRD': NCCRDInnerConfig,
    }


nccrd_config = NCCRDRootConfig()

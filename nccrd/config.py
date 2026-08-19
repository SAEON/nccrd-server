from odp.config import BaseConfig
from odp.config.mixins import DBConfigMixin


class NCCRDDBConfig(BaseConfig, DBConfigMixin):
    class Config:
        env_prefix = 'NCCRD_DB_'


class NCCRDInnerConfig(BaseConfig):
    class Config:
        env_prefix = 'NCCRD_'

    API_URL: str = None

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

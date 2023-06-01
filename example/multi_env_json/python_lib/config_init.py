# -*- coding: utf-8 -*-

from .config_paths import (
    path_config_v1,
    path_config_secret_v1,
    path_config_v2,
    path_config_secret_v2,
    path_config_v3,
    path_config_secret_v3,
)
from .config_define import (
    EnvEnum,
    Env,
    Config,
)

mapper = {
    "v1": (
        path_config_v1,
        path_config_secret_v1,
    ),
    "v2": (
        path_config_v2,
        path_config_secret_v2,
    ),
    "v3": (
        path_config_v3,
        path_config_secret_v3,
    ),
}


def read_config_from_file(version: str) -> Config:
    return Config.read(
        env_class=Env,
        env_enum_class=EnvEnum,
        path_config=mapper[version][0],
        path_secret_config=mapper[version][1],
    )

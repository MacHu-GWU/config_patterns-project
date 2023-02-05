# content of config_define.py
# -*- coding: utf-8 -*-

import typing as T
import dataclasses

from config_patterns.patterns.multi_env_json import (
    BaseEnvEnum,
    BaseEnv,
    BaseConfig,
)


class EnvEnum(BaseEnvEnum):
    dev = "dev" # development
    int = "int" # integration test
    prod = "prod" # production


@dataclasses.dataclass
class Env(BaseEnv):
    username: T.Optional[str] = dataclasses.field(default=None)
    password: T.Optional[str] = dataclasses.field(default=None)


@dataclasses.dataclass
class Config(BaseConfig):
    @property
    def dev(self) -> Env:
        return self.get_env(EnvEnum.dev)

    @property
    def int(self) -> Env:
        return self.get_env(EnvEnum.int)

    @property
    def prod(self) -> Env:
        return self.get_env(EnvEnum.prod)
# content of config_define.py
# -*- coding: utf-8 -*-

import typing as T
import dataclasses

from config_patterns.patterns.multi_env_json.api import (
    BaseEnvEnum,
    BaseEnv,
    BaseConfig,
    normalize_parameter_name,
)


class EnvEnum(BaseEnvEnum):
    dev = "dev"  # development
    prod = "prod"  # production


@dataclasses.dataclass
class Env(BaseEnv):
    username: T.Optional[str] = dataclasses.field(default=None)
    password: T.Optional[str] = dataclasses.field(default=None)

    @property
    def parameter_name(self) -> str:
        return f"{normalize_parameter_name(self.prefix_name_snake)}"
        # return f"/app/{normalize_parameter_name(self.prefix_name_snake)}"

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclasses.dataclass
class Config(BaseConfig):
    @property
    def dev(self) -> Env:
        return self.get_env(EnvEnum.dev)

    @property
    def prod(self) -> Env:
        return self.get_env(EnvEnum.prod)

    @classmethod
    def get_current_env(cls) -> str:
        return EnvEnum.dev.value

    @property
    def parameter_name(self) -> str:
        return f"{normalize_parameter_name(self.project_name_snake)}"
        # return f"/app/{normalize_parameter_name(self.project_name_snake)}"

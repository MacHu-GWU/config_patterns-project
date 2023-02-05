# -*- coding: utf-8 -*-

import typing as T
import dataclasses

from config_patterns.patterns.multi_env_json import (
    BaseEnvEnum,
    BaseEnv,
    BaseConfig,
)


class EnvEnum(BaseEnvEnum):
    dev = "dev"
    int = "int"
    prod = "prod"


@dataclasses.dataclass
class Env(BaseEnv):
    username: T.Optional[str] = dataclasses.field(default=None)
    password: T.Optional[str] = dataclasses.field(default=None)


@dataclasses.dataclass
class Config(BaseConfig):
    EnvEnum = EnvEnum
    Env = Env


if __name__ == "__main__":
    from rich import print as rprint
    from pathlib import Path
    from boto_session_manager import BotoSesManager

    dir_here = Path(__file__).absolute().parent
    path_config = str(dir_here.joinpath("config.json"))
    path_secret_config = str(dir_here.joinpath("secret_config.json"))

    bsm = BotoSesManager(profile_name="aws_data_lab_sanhe_us_east_1")
    s3dir_config = "s3://669508176277-us-east-1-artifacts/projects/config_pattern/patterns/multi_env_json/"

    # config = Config.read(
    #     env_class=Env,
    #     env_enum_class=EnvEnum,
    # ) # this will faile

    config = Config.read(
        env_class=Env,
        env_enum_class=EnvEnum,
        path_config=path_config,
        path_secret_config=path_secret_config,
    )
    rprint(config)

    # config.deploy() # this will faile

    config.deploy(
        bsm=bsm,
        parameter_with_encryption=True,
    )

    config.deploy(
        bsm=bsm,
        s3dir_config="s3://669508176277-us-east-1-artifacts/projects/config_pattern/patterns/multi_env_json/",
    )

    config = Config.read(
        env_class=Env,
        env_enum_class=EnvEnum,
        parameter_name="my_project-dev",
        parameter_with_encryption=True,
    )
    rprint(config)

    config = Config.read(
        env_class=Env,
        env_enum_class=EnvEnum,
        s3path_config=f"{s3dir_config}dev.json",
    )
    rprint(config)

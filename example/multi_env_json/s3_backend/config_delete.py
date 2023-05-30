# content of config_deploy.py
# -*- coding: utf-8 -*-

# import from the config_define.py
from config_define import EnvEnum, Env, Config

import os
from pathlib import Path
from boto_session_manager import BotoSesManager
from rich import print as rprint

# Read config from local file
dir_here = Path(os.getcwd())
path_config = str(dir_here.joinpath("data", "v1", "config.json"))
path_secret_config = str(dir_here.joinpath("data", "v1", "config_secret.json"))


config = Config.read(
    env_class=Env,
    env_enum_class=EnvEnum,
    path_config=path_config,
    path_secret_config=path_secret_config,
)
# rprint(config)


# Delete config from AWS Parameter Store
bsm = BotoSesManager(profile_name="opensource")
s3folder_config = f"s3://{bsm.aws_account_id}-us-east-1-artifacts/projects/config_pattern/patterns/multi_env_json/"

config.delete(
    bsm=bsm,
    s3folder_config=s3folder_config,
)

config.delete(
    bsm=bsm,
    s3folder_config=s3folder_config,
    include_history=True,
)

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

def read_config_from_file(version: str) -> Config:
    path_config = str(dir_here.joinpath("data", version, "config.json"))
    path_secret_config = str(dir_here.joinpath("data", version, "config_secret.json"))
    config = Config.read(
        env_class=Env,
        env_enum_class=EnvEnum,
        path_config=path_config,
        path_secret_config=path_secret_config,
    )
    return config


bsm = BotoSesManager(profile_name="opensource")
s3folder_config = f"s3://{bsm.aws_account_id}-us-east-1-versioned-artifacts/projects/config_pattern/patterns/multi_env_json/"

# --- v1
config_v1 = read_config_from_file(version="v1")
# rprint(config_v1)
config_v1.delete(
    bsm=bsm,
    s3folder_config=s3folder_config,
    include_history=True,
    verbose=False,
)
deployment_list = config_v1.deploy(
    bsm=bsm,
    s3folder_config=s3folder_config,
    verbose=True,
)
# rprint(deployment_list)
config_v1.deploy(
    bsm=bsm,
    s3folder_config=s3folder_config,
    verbose=True,
)

# --- v2
config_v2 = read_config_from_file(version="v2")
# # rprint(config_v2)
deployment_list = config_v2.deploy(
    bsm=bsm,
    s3folder_config=s3folder_config,
    verbose=True,
)
# rprint(deployment_list)

config_v2.delete(bsm=bsm, s3folder_config=s3folder_config)

# --- v3
config_v3 = read_config_from_file(version="v3")
# # rprint(config_v2)
deployment_list = config_v3.deploy(
    bsm=bsm,
    s3folder_config=s3folder_config,
    verbose=True,
)
# rprint(deployment_list)

# --- clean up
config_v2.delete(bsm=bsm, s3folder_config=s3folder_config)
config_v2.delete(bsm=bsm, s3folder_config=s3folder_config, include_history=True)

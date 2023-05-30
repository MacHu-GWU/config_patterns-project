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
path_config = str(dir_here.joinpath("config.json"))
path_secret_config = str(dir_here.joinpath("secret_config.json"))


config = Config.read(
    env_class=Env,
    env_enum_class=EnvEnum,
    path_config=path_config,
    path_secret_config=path_secret_config,
)
# rprint(config)


bsm = BotoSesManager(profile_name="opensource")

# --- Deploy config to AWS Parameter Store
# config.delete(
#     bsm=bsm,
#     use_parameter_store=True,
#     verbose=True,
# )
# deployment_list = config.deploy(
#     bsm=bsm,
#     parameter_with_encryption=True,
#     verbose=True,
# )
# config = Config.read(
#     env_class=Env,
#     env_enum_class=EnvEnum,
#     bsm=bsm,
#     parameter_name="/app/my_project-dev",
#     parameter_with_encryption=True,
# )
# print(config.dev.username)
# print(config.dev.password)
# rprint(deployment_list)

# --- Deploy config to AWS S3 Store
s3folder_config = f"s3://{bsm.aws_account_id}-us-east-1-artifacts/projects/config_pattern/patterns/multi_env_json/"
print(config.parameter_name)
config.delete(
    bsm=bsm,
    s3folder_config=s3folder_config,
    verbose=False,
)
deployment_list = config.deploy(
    bsm=bsm,
    s3folder_config=s3folder_config,
    verbose=True,
)
# rprint(deployment_list)

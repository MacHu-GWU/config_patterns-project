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
rprint(config)


# Deploy config to AWS Parameter Store
bsm = BotoSesManager(profile_name="aws_data_lab_sanhe_us_east_1")
s3dir_config = "s3://669508176277-us-east-1-artifacts/projects/config_pattern/patterns/multi_env_json/"


deployment_list = config.deploy(
    bsm=bsm,
    parameter_with_encryption=True,
)
rprint(deployment_list)

# Deploy config to AWS S3 Store
deployment_list = config.deploy(
    bsm=bsm,
    s3dir_config=s3dir_config,
)
rprint(deployment_list)

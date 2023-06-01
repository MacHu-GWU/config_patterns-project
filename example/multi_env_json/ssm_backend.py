# content of config_deploy.py
# -*- coding: utf-8 -*-

from python_lib.config_init import (
    read_config_from_file,
    EnvEnum,
    Env,
    Config,
)
from boto_session_manager import BotoSesManager
from rich import print as rprint

bsm = BotoSesManager(profile_name="opensource")

config_v1 = read_config_from_file("v1")

# --- clean up existing deployment
config_v1.delete(
    bsm=bsm,
    use_parameter_store=True,
    verbose=False,
)

# --- Deploy config to AWS Parameter Store
deployment_list = config_v1.deploy(
    bsm=bsm,
    parameter_with_encryption=True,
    tags={"version": "v1"},
    # verbose=True,
    verbose=False,
)
# rprint(deployment_list)

# --- Deploy the same data to AWS Parameter Store, it should do nothing
config_v1.deploy(
    bsm=bsm,
    parameter_with_encryption=True,
    # verbose=True,
    verbose=False,
)

# --- Read config from AWS Parameter Store
config = Config.read(
    env_class=Env,
    env_enum_class=EnvEnum,
    bsm=bsm,
    parameter_name=config_v1.parameter_name,
    parameter_with_encryption=True,
)
# rprint(config)
# rprint(config._merged)

# --- Deploy a new version to AWS Parameter Store
config_v2 = read_config_from_file("v2")
deployment_list = config_v2.deploy(
    bsm=bsm,
    parameter_with_encryption=True,
    tags={"version": "v2"},
    # verbose=True,
    verbose=False,
)
# rprint(deployment_list)

# --- Read config from AWS Parameter Store
config = Config.read(
    env_class=Env,
    env_enum_class=EnvEnum,
    bsm=bsm,
    parameter_name=config_v2.parameter_name,
    parameter_with_encryption=True,
)
# rprint(config)
# rprint(config._merged)

# --- Delete config from AWS Parameter Store
config.delete(
    bsm=bsm,
    use_parameter_store=True,
    verbose=True,
    # verbose=False,
)

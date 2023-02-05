# content of config_init.py
# -*- coding: utf-8 -*-

from config_define import EnvEnum, Env, Config

from rich import print as rprint
from boto_session_manager import BotoSesManager

# create boto session manager object for AWS SDK authentication
bsm = BotoSesManager(profile_name="aws_data_lab_sanhe_us_east_1")
parameter_name = "my_project-dev"
s3dir_config = "s3://669508176277-us-east-1-artifacts/projects/config_pattern/patterns/multi_env_json/"

config = Config.read(
    env_class=Env,
    env_enum_class=EnvEnum,
    parameter_name=parameter_name,
    parameter_with_encryption=True,
)
rprint(config)
print(f"config.dev.username = {config.dev.username}")
print(f"config.dev.password = {config.dev.password}")

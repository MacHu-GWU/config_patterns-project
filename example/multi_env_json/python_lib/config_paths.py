# -*- coding: utf-8 -*-

from pathlib import Path

dir_multi_env_json = Path(__file__).absolute().parent.parent
dir_sample_data = dir_multi_env_json.joinpath("sample-data")

path_config_v1 = dir_sample_data.joinpath("v1", "config.json")
path_config_secret_v1 = dir_sample_data.joinpath("v1", "config_secret.json")
path_config_v2 = dir_sample_data.joinpath("v2", "config.json")
path_config_secret_v2 = dir_sample_data.joinpath("v2", "config_secret.json")
path_config_v3 = dir_sample_data.joinpath("v3", "config.json")
path_config_secret_v3 = dir_sample_data.joinpath("v3", "config_secret.json")
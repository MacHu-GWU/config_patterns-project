# -*- coding: utf-8 -*-

from config_patterns import api

def test():
    _ = api.hierarchy
    _ = api.hierarchy.SHARED
    _ = api.hierarchy.inherit_shared_value
    _ = api.hierarchy.apply_shared_value

    _ = api.merge_key_value
    _ = api.merge_key_value.merge_key_value

    _ = api.multi_env_json
    _ = api.multi_env_json.ALL
    _ = api.multi_env_json.BaseEnvEnum
    _ = api.multi_env_json.BaseEnv
    _ = api.multi_env_json.BaseConfig
    _ = api.multi_env_json.normalize_parameter_name
    _ = api.multi_env_json.ConfigDeployment


if __name__ == "__main__":
    from config_patterns.tests import run_cov_test

    run_cov_test(__file__, "config_patterns.api", preview=False)
# -*- coding: utf-8 -*-

"""
Usage example::

    import config_pattern.api as config_pattern

    config_pattern.hierarchy.SHARED
    config_pattern.hierarchy.inherit_shared_value
    config_pattern.hierarchy.apply_shared_value
    config_pattern.merge_key_value.merge_key_value
    config_pattern.multi_env_json.ALL
    config_pattern.multi_env_json.BaseEnvEnum
    config_pattern.multi_env_json.BaseEnv
    config_pattern.multi_env_json.BaseConfig
    config_pattern.multi_env_json.normalize_parameter_name
    config_pattern.multi_env_json.ConfigDeployment
"""

from .patterns.hierarchy import api as hierarchy
from .patterns.merge_key_value import api as merge_key_value

try:
    from .patterns.multi_env_json import api as multi_env_json
except ImportError: # pragma: no cover
    pass

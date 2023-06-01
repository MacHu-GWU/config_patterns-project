# -*- coding: utf-8 -*-

from .patterns.hierarchy import api as hierarchy
from .patterns.merge_key_value import api as merge_key_value

try:
    from .patterns.multi_env_json import api as multi_env_json
except ImportError: # pragma: no cover
    pass

# -*- coding: utf-8 -*-

import json
import hashlib

def sha256_of_text(s: str) -> str:
    m = hashlib.sha256()
    m.update(s.encode('utf-8'))
    return m.hexdigest()

def sha256_of_config_data(data: dict) -> str:
    return sha256_of_text(json.dumps(data, sort_keys=True))

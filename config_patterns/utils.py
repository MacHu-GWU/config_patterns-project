# -*- coding: utf-8 -*-

import hashlib

def sha256_of_text(s: str) -> str:
    m = hashlib.sha256()
    m.update(s.encode('utf-8'))
    return m.hexdigest()

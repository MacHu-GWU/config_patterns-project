# -*- coding: utf-8 -*-

import pytest
from config_patterns.patterns.merge_key_value.api import merge_key_value


def test_merge_key_value():
    data1 = {
        "dev": {
            "username": "dev.user",
        },
        "test": {
            "username": "test.user",
            "server": {
                "username": "ubuntu",
            },
            "databases": [
                {"host": "www.db1.com", "username": "admin"},
                {"host": "www.db2.com", "username": "admin"},
            ],
        },
    }
    data2 = {
        "test": {
            "password": "test.password",
            "server": {
                "password": "ubuntu.password",
            },
            "databases": [
                {"password": "db1pwd"},
                {"password": "db2pwd"},
            ],
        },
        "prod": {
            "password": "prod.password",
        },
    }
    data = merge_key_value(data1, data2)
    assert data == {
        "dev": {"username": "dev.user"},
        "test": {
            "username": "test.user",
            "server": {"username": "ubuntu", "password": "ubuntu.password"},
            "databases": [
                {"host": "www.db1.com", "username": "admin", "password": "db1pwd"},
                {"host": "www.db2.com", "username": "admin", "password": "db2pwd"},
            ],
            "password": "test.password",
        },
        "prod": {"password": "prod.password"},
    }

    data1 = {
        "tags": [
            {"key1": "value1"},
        ]
    }
    data2 = {
        "tags": [
            {"key2": "value2"},
            {"key2": "value2"},
        ]
    }
    with pytest.raises(ValueError):
        merge_key_value(data1, data2)

    with pytest.raises(TypeError):
        merge_key_value({"values": [1, 2]}, {"values": [2, 3]})

    with pytest.raises(TypeError):
        merge_key_value({"value": 1}, {"value": 2})


if __name__ == "__main__":
    from config_patterns.tests import run_cov_test

    run_cov_test(__file__, "config_patterns.patterns.merge_key_value", preview=False)

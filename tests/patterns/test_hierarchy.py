# -*- coding: utf-8 -*-

import copy

import pytest

from config_patterns.patterns.hierarchy.api import (
    inherit_shared_value,
    apply_shared_value,
)


def _test_inherit_shared_value_with_multi_parts_path():
    data = {"key1": "value1"}
    inherit_shared_value(path="key1", value="invalid", data=data)
    assert data["key1"] == "value1" # no change
    inherit_shared_value(path="key2", value="value2", data=data)
    assert data["key2"] == "value2" # new key

    data = {"key1": {"key11": "value11"}}
    inherit_shared_value(path="key1.key11", value="invalid", data=data)
    assert data["key1"]["key11"] == "value11" # no change
    inherit_shared_value(path="key1.key12", value="value12", data=data)
    assert data["key1"]["key12"] == "value12" # new key

    data = {"key1": {"key11": {"key111": "value111"}}}
    inherit_shared_value(path="key1.key11.key111", value="invalid", data=data)
    assert data["key1"]["key11"]["key111"] == "value111" # no change
    inherit_shared_value(path="key1.key11.key112", value="value112", data=data)
    assert data["key1"]["key11"]["key112"] == "value112" # new key


def _test_inherit_shared_value_in_list_of_dict():
    data = [
        {"key1": "value1"},
        {"key1": "value1"},
    ]
    inherit_shared_value(path="key1", value="invalid", data=data)
    assert data == [{"key1": "value1"}, {"key1": "value1"}]
    inherit_shared_value(path="key2", value="value2", data=data)
    assert data == [
        {"key1": "value1", "key2": "value2"},
        {"key1": "value1", "key2": "value2"},
    ]

    data = {
        "tags": [
            {"key1": "value1"},
            {"key1": "value1"},
        ],
    }
    inherit_shared_value(path="tags.key1", value="invalid", data=data)
    assert data["tags"] == [{"key1": "value1"}, {"key1": "value1"}]
    inherit_shared_value(path="tags.key2", value="value2", data=data)
    assert data["tags"] == [
        {"key1": "value1", "key2": "value2"},
        {"key1": "value1", "key2": "value2"},
    ]

    data = {
        "persons": [
            {
                "name": "alice",
                "tags": [
                    {"key1": "value1"},
                    {"key1": "value1"},
                ],
            },
            {
                "name": "bob",
                "tags": [
                    {"key1": "value1"},
                    {"key1": "value1"},
                ],
            },
        ],
    }
    inherit_shared_value(path="persons.tags.key2", value="value2", data=data)
    assert data["persons"][0]["tags"] == [
        {"key1": "value1", "key2": "value2"},
        {"key1": "value1", "key2": "value2"},
    ]
    assert data["persons"][1]["tags"] == [
        {"key1": "value1", "key2": "value2"},
        {"key1": "value1", "key2": "value2"},
    ]


def _test_inherit_shared_value_with_star_notation():
    data = {
        "dev": {"key1": "dev_value1"},
        "prod": {"key1": "prod_value1"},
    }
    inherit_shared_value(path="*.key1", value="invalid", data=data)
    assert data["dev"]["key1"] == "dev_value1"
    assert data["prod"]["key1"] == "prod_value1"
    inherit_shared_value(path="*.key2", value="value2", data=data)
    assert data["dev"]["key2"] == "value2"
    assert data["prod"]["key2"] == "value2"

    data = {
        "envs": {
            "dev": {"key1": "dev_value1"},
            "prod": {"key1": "prod_value1"},
        }
    }
    inherit_shared_value(path="envs.*.key1", value="invalid", data=data)
    assert data["envs"]["dev"]["key1"] == "dev_value1"
    assert data["envs"]["prod"]["key1"] == "prod_value1"
    inherit_shared_value(path="envs.*.key2", value="value2", data=data)
    assert data["envs"]["dev"]["key2"] == "value2"
    assert data["envs"]["prod"]["key2"] == "value2"

    raw_data = {
        "envs": {
            "dev": {
                "server": {
                    "blue": {"key1": "dev_blue_value1"},
                    "green": {"key1": "dev_green_value1"},
                }
            },
            "prod": {
                "server": {
                    "black": {"key1": "prod_black_value1"},
                    "white": {"key1": "prod_white_value1"},
                }
            },
        }
    }

    data = copy.deepcopy(raw_data)
    inherit_shared_value(path="envs.*.server.*.key1", value="value2", data=data)
    assert data["envs"]["dev"]["server"]["blue"]["key1"] == "dev_blue_value1"
    assert data["envs"]["dev"]["server"]["green"]["key1"] == "dev_green_value1"
    assert data["envs"]["prod"]["server"]["black"]["key1"] == "prod_black_value1"
    assert data["envs"]["prod"]["server"]["white"]["key1"] == "prod_white_value1"
    inherit_shared_value(path="envs.*.server.*.key2", value="value2", data=data)
    assert data["envs"]["dev"]["server"]["blue"]["key2"] == "value2"
    assert data["envs"]["dev"]["server"]["green"]["key2"] == "value2"
    assert data["envs"]["prod"]["server"]["black"]["key2"] == "value2"
    assert data["envs"]["prod"]["server"]["white"]["key2"] == "value2"

    data = copy.deepcopy(raw_data)
    inherit_shared_value(path="envs.dev.server.*.key1", value="value2", data=data)
    assert data["envs"]["dev"]["server"]["blue"]["key1"] == "dev_blue_value1"
    assert data["envs"]["dev"]["server"]["green"]["key1"] == "dev_green_value1"
    assert data["envs"]["prod"]["server"]["black"]["key1"] == "prod_black_value1"
    assert data["envs"]["prod"]["server"]["white"]["key1"] == "prod_white_value1"
    inherit_shared_value(path="envs.dev.server.*.key2", value="value2", data=data)
    assert data["envs"]["dev"]["server"]["blue"]["key2"] == "value2"
    assert data["envs"]["dev"]["server"]["green"]["key2"] == "value2"
    assert "key2" not in data["envs"]["prod"]["server"]["black"]
    assert "key2" not in data["envs"]["prod"]["server"]["white"]

    raw_data = {
        "envs": {
            "dev": {
                "server": {
                    "blue": {
                        "tags": [
                            {"key1": "dev_blue_value1"},
                        ],
                    },
                    "green": {
                        "tags": [
                            {"key1": "dev_green_value1"},
                        ],
                    },
                }
            },
            "prod": {
                "server": {
                    "black": {
                        "tags": [
                            {"key1": "prod_black_value1"},
                        ],
                    },
                    "white": {
                        "tags": [
                            {"key1": "prod_white_value1"},
                        ],
                    },
                }
            },
        }
    }
    data = copy.deepcopy(raw_data)

    inherit_shared_value(path="envs.*.server.*.tags.key1", value="invalid", data=data)
    dev, prod = data["envs"]["dev"], data["envs"]["prod"]
    assert dev["server"]["blue"]["tags"][0]["key1"] == "dev_blue_value1"
    assert dev["server"]["green"]["tags"][0]["key1"] == "dev_green_value1"
    assert prod["server"]["black"]["tags"][0]["key1"] == "prod_black_value1"
    assert prod["server"]["white"]["tags"][0]["key1"] == "prod_white_value1"

    inherit_shared_value(path="envs.*.server.*.tags.key2", value="value2", data=data)
    dev, prod = data["envs"]["dev"], data["envs"]["prod"]
    assert dev["server"]["blue"]["tags"][0]["key2"] == "value2"
    assert dev["server"]["green"]["tags"][0]["key2"] == "value2"
    assert prod["server"]["black"]["tags"][0]["key2"] == "value2"
    assert prod["server"]["white"]["tags"][0]["key2"] == "value2"


def _test_inherit_shared_value_edge_cases():
    data = {"key1": "value1"}

    with pytest.raises(ValueError):
        inherit_shared_value(path="*", value="value", data={"k1": "v1"})

    with pytest.raises(TypeError):
        inherit_shared_value(path="k1", value="v1", data="hello")

    with pytest.raises(TypeError):
        inherit_shared_value(path="k1", value="v1", data=(1, 2, 3))

    with pytest.raises(TypeError):
        inherit_shared_value(path="k1.k11", value="v11", data={"k1": "v1"})

    with pytest.raises(TypeError):
        inherit_shared_value(path="k1.k11", value="v11", data={"k1": [1, 2, 3]})

    with pytest.raises(TypeError):
        inherit_shared_value(path="k1.k11", value="v11", data="hello")

    with pytest.raises(TypeError):
        inherit_shared_value(path="k1.k11.k111", value="v111", data={"k1": {"k11": "v11"}})


def test_inherit_shared_value():
    _test_inherit_shared_value_with_multi_parts_path()
    _test_inherit_shared_value_in_list_of_dict()
    _test_inherit_shared_value_with_star_notation()
    _test_inherit_shared_value_edge_cases()


def test_apply_shared_value():
    data = {
        "_shared": {
            "*.key2": "value2",
            "*.a_dict.key2": "value2",
            "*.servers.*.cpu": 1,
            "*.databases.port": 1,
        },
        "dev": {
            "key1": "dev_value1",
            "a_dict": {
                "key1": "dev_value1",
            },
            "servers": {
                "_shared": {
                    "*.cpu": 2,
                },
                "blue": {},
                "green": {"cpu": 4},
            },
            "databases": [
                {"host": "db1.com"},
                {"host": "db2.com", "port": 2},
            ],
        },
        "prod": {
            "_shared": {
                "databases.port": 3,
            },
            "key1": "prod_value1",
            "a_dict": {
                "key1": "prod_value1",
            },
            "servers": {
                "black": {},
                "white": {"cpu": 8},
            },
            "databases": [
                {"host": "db3.com"},
                {"host": "db4.com", "port": 4},
            ],
        },
    }
    apply_shared_value(data)
    assert data == {
        "dev": {
            "key1": "dev_value1",
            "key2": "value2",
            "a_dict": {
                "key1": "dev_value1",
                "key2": "value2",
            },
            "servers": {
                "blue": {"cpu": 2},
                "green": {"cpu": 4},
            },
            "databases": [
                {"host": "db1.com", "port": 1},
                {"host": "db2.com", "port": 2},
            ],
        },
        "prod": {
            "key1": "prod_value1",
            "key2": "value2",
            "a_dict": {
                "key1": "prod_value1",
                "key2": "value2",
            },
            "servers": {
                "black": {"cpu": 1},
                "white": {"cpu": 8},
            },
            "databases": [
                {"host": "db3.com", "port": 3},
                {"host": "db4.com", "port": 4},
            ],
        },
    }


if __name__ == "__main__":
    from config_patterns.tests import run_cov_test

    run_cov_test(__file__, "config_patterns.patterns.hierarchy", preview=False)

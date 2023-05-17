# -*- coding: utf-8 -*-

import typing as T
import pytest
import copy
import json
import dataclasses
from pathlib import Path

import moto
from boto_session_manager import BotoSesManager
from rich import print as rprint

from config_patterns.patterns.multi_env_json import (
    validate_project_name,
    validate_env_name,
    set_shared_value,
    apply_shared_value,
    merge_key_value,
    normalize_parameter_name,
    BaseEnvEnum,
    BaseEnv,
    BaseConfig,
)
from config_patterns.logger import logger


class EnvEnum(BaseEnvEnum):
    dev = "dev"  # development
    prod = "prod"  # production


@dataclasses.dataclass
class Server:
    ip: T.Optional[str] = dataclasses.field(default=None)
    cpu: T.Optional[int] = dataclasses.field(default=None)
    memory: T.Optional[int] = dataclasses.field(default=None)
    domain: T.Optional[str] = dataclasses.field(default=None)


@dataclasses.dataclass
class Servers:
    blue: T.Optional[Server] = dataclasses.field(default=None)
    green: T.Optional[Server] = dataclasses.field(default=None)
    black: T.Optional[Server] = dataclasses.field(default=None)
    white: T.Optional[Server] = dataclasses.field(default=None)

    @classmethod
    def from_dict(cls, data: dict):
        for field in dataclasses.fields(cls):
            if field.name in data:
                data[field.name] = Server(**data[field.name])
        return cls(**data)


@dataclasses.dataclass
class Database:
    host: T.Optional[str] = dataclasses.field(default=None)
    port: T.Optional[int] = dataclasses.field(default=None)
    password: T.Optional[str] = dataclasses.field(default=None)


@dataclasses.dataclass
class Env(BaseEnv):
    username: T.Optional[str] = dataclasses.field(default=None)
    password: T.Optional[str] = dataclasses.field(default=None)
    tags: T.Dict[str, str] = dataclasses.field(default_factory=dict)
    servers: T.Optional[Servers] = dataclasses.field(default=None)
    databases: T.List[Database] = dataclasses.field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Env":
        data["servers"] = Servers.from_dict(data.get("servers", {}))
        data["databases"] = [Database(**dct) for dct in data.get("databases", [])]
        return cls(**data)


@dataclasses.dataclass
class Config(BaseConfig):
    @classmethod
    def get_current_env(cls) -> str:
        return EnvEnum.dev.value

    @property
    def dev(self) -> Env:
        return self.get_env(EnvEnum.dev)

    @property
    def prod(self) -> Env:
        return self.get_env(EnvEnum.prod)

    @property
    def env(self) -> Env:
        return self.get_env(env_name=self.get_current_env())


class TestBaseEnvEnum:
    def test(self):
        assert EnvEnum.dev == "dev"
        assert EnvEnum.ensure_str("dev") == "dev"
        assert EnvEnum.ensure_str(EnvEnum.dev) == "dev"


def test_validate_project_name():
    good_cases = [
        "my_project",
        "my-project",
        "my_1_project",
        "my1project",
        "myproject1",
    ]
    bad_cases = [
        "my project",
        "1-my-project",
        "-my-project",
        "my-project-",
    ]
    for project_name in good_cases:
        validate_project_name(project_name)
    for project_name in bad_cases:
        with pytest.raises(ValueError):
            validate_project_name(project_name)


def test_validate_env_name():
    good_cases = [
        "dev",
        "test",
        "prod",
        "stage1",
        "stage2",
    ]
    bad_cases = [
        "my_dev",
        "my-dev",
        "dev_",
        "dev-",
        "1dev",
    ]
    for env_name in good_cases:
        validate_env_name(env_name)
    for env_name in bad_cases:
        with pytest.raises(ValueError):
            validate_env_name(env_name)


def test_normalize_parameter_name():
    assert normalize_parameter_name("aws") == "p-aws"
    assert normalize_parameter_name("aws-project") == "p-aws-project"
    assert normalize_parameter_name("ssm") == "p-ssm"
    assert normalize_parameter_name("ssm-project") == "p-ssm-project"


def _test_set_shared_value_multi_parts_path():
    data = {"key1": "value1"}
    set_shared_value(path="key1", value="invalid", data=data)
    assert data["key1"] == "value1"
    set_shared_value(path="key2", value="value2", data=data)
    assert data["key2"] == "value2"

    data = {"key1": {"key11": "value11"}}
    set_shared_value(path="key1.key11", value="invalid", data=data)
    assert data["key1"]["key11"] == "value11"
    set_shared_value(path="key1.key12", value="value12", data=data)
    assert data["key1"]["key12"] == "value12"

    data = {"key1": {"key11": {"key111": "value111"}}}
    set_shared_value(path="key1.key11.key111", value="invalid", data=data)
    assert data["key1"]["key11"]["key111"] == "value111"
    set_shared_value(path="key1.key11.key112", value="value112", data=data)
    assert data["key1"]["key11"]["key112"] == "value112"


def _test_set_shared_value_list():
    data = [
        {"key1": "value1"},
        {"key1": "value1"},
    ]
    set_shared_value(path="key1", value="invalid", data=data)
    assert data == [{"key1": "value1"}, {"key1": "value1"}]
    set_shared_value(path="key2", value="value2", data=data)
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
    set_shared_value(path="tags.key1", value="invalid", data=data)
    assert data["tags"] == [{"key1": "value1"}, {"key1": "value1"}]
    set_shared_value(path="tags.key2", value="value2", data=data)
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
    set_shared_value(path="persons.tags.key2", value="value2", data=data)
    assert data["persons"][0]["tags"] == [
        {"key1": "value1", "key2": "value2"},
        {"key1": "value1", "key2": "value2"},
    ]
    assert data["persons"][1]["tags"] == [
        {"key1": "value1", "key2": "value2"},
        {"key1": "value1", "key2": "value2"},
    ]


def _test_set_shared_value_star_notation():
    data = {
        "dev": {"key1": "dev_value1"},
        "prod": {"key1": "prod_value1"},
    }
    set_shared_value(path="*.key1", value="invalid", data=data)
    assert data["dev"]["key1"] == "dev_value1"
    assert data["prod"]["key1"] == "prod_value1"
    set_shared_value(path="*.key2", value="value2", data=data)
    assert data["dev"]["key2"] == "value2"
    assert data["prod"]["key2"] == "value2"

    data = {
        "envs": {
            "dev": {"key1": "dev_value1"},
            "prod": {"key1": "prod_value1"},
        }
    }
    set_shared_value(path="envs.*.key1", value="invalid", data=data)
    assert data["envs"]["dev"]["key1"] == "dev_value1"
    assert data["envs"]["prod"]["key1"] == "prod_value1"
    set_shared_value(path="envs.*.key2", value="value2", data=data)
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
    set_shared_value(path="envs.*.server.*.key1", value="value2", data=data)
    assert data["envs"]["dev"]["server"]["blue"]["key1"] == "dev_blue_value1"
    assert data["envs"]["dev"]["server"]["green"]["key1"] == "dev_green_value1"
    assert data["envs"]["prod"]["server"]["black"]["key1"] == "prod_black_value1"
    assert data["envs"]["prod"]["server"]["white"]["key1"] == "prod_white_value1"
    set_shared_value(path="envs.*.server.*.key2", value="value2", data=data)
    assert data["envs"]["dev"]["server"]["blue"]["key2"] == "value2"
    assert data["envs"]["dev"]["server"]["green"]["key2"] == "value2"
    assert data["envs"]["prod"]["server"]["black"]["key2"] == "value2"
    assert data["envs"]["prod"]["server"]["white"]["key2"] == "value2"

    data = copy.deepcopy(raw_data)
    set_shared_value(path="envs.dev.server.*.key1", value="value2", data=data)
    assert data["envs"]["dev"]["server"]["blue"]["key1"] == "dev_blue_value1"
    assert data["envs"]["dev"]["server"]["green"]["key1"] == "dev_green_value1"
    assert data["envs"]["prod"]["server"]["black"]["key1"] == "prod_black_value1"
    assert data["envs"]["prod"]["server"]["white"]["key1"] == "prod_white_value1"
    set_shared_value(path="envs.dev.server.*.key2", value="value2", data=data)
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
    set_shared_value(path="envs.*.server.*.tags.key1", value="invalid", data=data)
    assert data["envs"]["dev"]["server"]["blue"]["tags"][0]["key1"] == "dev_blue_value1"
    assert (
        data["envs"]["dev"]["server"]["green"]["tags"][0]["key1"] == "dev_green_value1"
    )
    assert (
        data["envs"]["prod"]["server"]["black"]["tags"][0]["key1"]
        == "prod_black_value1"
    )
    assert (
        data["envs"]["prod"]["server"]["white"]["tags"][0]["key1"]
        == "prod_white_value1"
    )
    set_shared_value(path="envs.*.server.*.tags.key2", value="value2", data=data)
    assert data["envs"]["dev"]["server"]["blue"]["tags"][0]["key2"] == "value2"
    assert data["envs"]["dev"]["server"]["green"]["tags"][0]["key2"] == "value2"
    assert data["envs"]["prod"]["server"]["black"]["tags"][0]["key2"] == "value2"
    assert data["envs"]["prod"]["server"]["white"]["tags"][0]["key2"] == "value2"


def test_set_shared_value():
    _test_set_shared_value_multi_parts_path()
    _test_set_shared_value_list()
    _test_set_shared_value_star_notation()


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

    with pytest.raises(ValueError):
        merge_key_value({"values": [1, 2]}, {"values": [2, 3]})

    with pytest.raises(TypeError):
        merge_key_value({"value": 1}, {"value": 2})


dir_here = Path(__file__).absolute().parent
path_config = str(dir_here.joinpath("config.json"))
path_secret_config = str(dir_here.joinpath("secret_config.json"))
path_merged_data = str(dir_here.joinpath("merged_data.json"))
path_merged_secret_data = str(dir_here.joinpath("merged_secret_data.json"))
path_merged = str(dir_here.joinpath("merged.json"))


class TestConfig:
    def test(self):
        with pytest.raises(ValueError):
            Config.read(
                env_class=Env,
                env_enum_class=EnvEnum,
            )

        config = Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            path_config=path_config,
            path_secret_config=path_secret_config,
        )

        assert config._merged_data == json.load(open(path_merged_data))
        assert config._merged_secret_data == json.load(open(path_merged_secret_data))
        assert config._merged == json.load(open(path_merged))

        assert config.project_name_slug == "my-project"
        assert config.project_name_snake == "my_project"
        assert config.parameter_name == "my_project"

        _ = config.dev
        _ = config.prod

        assert config.env.project_name_slug == "my-project"
        assert config.env.project_name_snake == "my_project"
        assert config.env.prefix_name_slug == "my-project-dev"
        assert config.env.prefix_name_snake == "my_project-dev"
        assert config.env.parameter_name == "my_project-dev"

        assert isinstance(config.env.tags, dict)
        assert isinstance(config.env.servers, Servers)
        assert isinstance(config.env.servers.blue, Server)
        assert config.env.servers.black is None
        assert isinstance(config.env.databases[0], Database)

    def test_unexpected_keyword_argument(self):
        @dataclasses.dataclass
        class Env(BaseEnv):
            username: T.Optional[str] = dataclasses.field(default=None)

            @classmethod
            def from_dict(cls, data: dict):
                return cls(**data)

        with pytest.raises(TypeError) as e:
            Config.read(
                env_class=Env,
                env_enum_class=EnvEnum,
                path_config=path_config,
                path_secret_config=path_secret_config,
            ).get_env(EnvEnum.dev.value)
            assert "please compare your config json file" in str(e)


class TestDeployment:
    mock_dynamodb = None
    bsm: BotoSesManager = None
    use_mock: bool = True

    @classmethod
    def setup_class(cls):
        if cls.use_mock:
            cls.mock_ssm = moto.mock_ssm()
            cls.mock_s3 = moto.mock_s3()
            cls.mock_ssm.start()
            cls.mock_s3.start()
        cls.bsm = BotoSesManager(region_name="us-east-1")
        cls.bsm.s3_client.create_bucket(Bucket="my-bucket")

    @classmethod
    def teardown_class(cls):
        if cls.use_mock:
            cls.mock_ssm.stop()
            cls.mock_s3.stop()

    def _test(self):
        config = Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            path_config=path_config,
            path_secret_config=path_secret_config,
        )

        config.delete(bsm=self.bsm, use_parameter_store=True)
        config.deploy(bsm=self.bsm, parameter_with_encryption=True)
        config1 = Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            bsm=self.bsm,
            parameter_name=config.parameter_name,
            parameter_with_encryption=True,
        )
        assert config1.data == config.data
        assert config1.secret_data == config.secret_data
        config.deploy(bsm=self.bsm, parameter_with_encryption=True)
        config.delete(bsm=self.bsm, use_parameter_store=True)

        s3dir_config = "s3://my-bucket/my-project/"
        config.delete(bsm=self.bsm, s3dir_config=s3dir_config)
        config.deploy(bsm=self.bsm, s3dir_config=s3dir_config)
        config1 = Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            bsm=self.bsm,
            s3path_config=f"{s3dir_config}{config.parameter_name}.json",
        )
        assert config1.data == config.data
        assert config1.secret_data == config.secret_data
        config.deploy(bsm=self.bsm, s3dir_config=s3dir_config)
        config.delete(bsm=self.bsm, s3dir_config=s3dir_config)

        with pytest.raises(ValueError):
            config.delete(bsm=self.bsm)

        with pytest.raises(ValueError):
            config.deploy(bsm=self.bsm, parameter_with_encryption="YES")

        with pytest.raises(ValueError):
            config.deploy(bsm=self.bsm)

    def test(self):
        with logger.disabled(
            disable=True,
            # disable=False,
        ):
            self._test()


if __name__ == "__main__":
    from config_patterns.tests import run_cov_test

    run_cov_test(__file__, "config_patterns.patterns.multi_env_json", preview=False)

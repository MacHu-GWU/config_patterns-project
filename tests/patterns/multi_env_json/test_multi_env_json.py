# -*- coding: utf-8 -*-

import typing as T
import pytest
import json
import dataclasses
from pathlib import Path

import moto
from boto_session_manager import BotoSesManager

from config_patterns.patterns.multi_env_json.impl import (
    validate_project_name,
    validate_env_name,
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

    run_cov_test(__file__, "config_patterns.patterns.multi_env_json.impl", preview=False)

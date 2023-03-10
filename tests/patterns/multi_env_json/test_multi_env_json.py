# -*- coding: utf-8 -*-

import typing as T
import pytest
import dataclasses
from pathlib import Path

from config_patterns.patterns.multi_env_json import (
    validate_project_name,
    validate_env_name,
    normalize_parameter_name,
    BaseEnvEnum,
    BaseEnv,
    BaseConfig,
)


class EnvEnum(BaseEnvEnum):
    dev = "dev"  # development
    int = "int"  # integration test
    prod = "prod"  # production


@dataclasses.dataclass
class Env(BaseEnv):
    username: T.Optional[str] = dataclasses.field(default=None)
    password: T.Optional[str] = dataclasses.field(default=None)


@dataclasses.dataclass
class Config(BaseConfig):
    @property
    def dev(self) -> Env:
        return self.get_env(EnvEnum.dev)

    @property
    def int(self) -> Env:
        return self.get_env(EnvEnum.int)

    @property
    def prod(self) -> Env:
        return self.get_env(EnvEnum.prod)

    @classmethod
    def get_current_env(cls) -> str:
        return EnvEnum.dev.value


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

        assert config.project_name_slug == "my-project"
        assert config.project_name_snake == "my_project"
        assert config.parameter_name == "my_project"

        _ = config.dev
        _ = config.int
        _ = config.prod

        assert config.env.project_name_slug == "my-project"
        assert config.env.project_name_snake == "my_project"
        assert config.env.prefix_name_slug == "my-project-dev"
        assert config.env.prefix_name_snake == "my_project-dev"
        assert config.env.parameter_name == "my_project-dev"

    def test_unexpected_keyword_argument(self):
        @dataclasses.dataclass
        class Env(BaseEnv):
            username: T.Optional[str] = dataclasses.field(default=None)

        with pytest.raises(TypeError) as e:
            Config.read(
                env_class=Env,
                env_enum_class=EnvEnum,
                path_config=path_config,
                path_secret_config=path_secret_config,
            ).get_env(EnvEnum.dev.value)
            assert "please compare your config json file" in str(e)


if __name__ == "__main__":
    from config_patterns.tests import run_cov_test

    run_cov_test(__file__, "config_patterns.patterns.multi_env_json", preview=False)

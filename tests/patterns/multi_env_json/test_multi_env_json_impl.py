# -*- coding: utf-8 -*-

import typing as T
import pytest
import json
import dataclasses
from pathlib import Path

import moto
from boto_session_manager import BotoSesManager
from s3pathlib import S3Path, context

from config_patterns import exc
from config_patterns.compat import cached_property
from config_patterns.aws.s3 import KEY_CONFIG_VERSION
from config_patterns.patterns.multi_env_json.impl import (
    ALL,
    validate_project_name,
    validate_env_name,
    normalize_parameter_name,
    BaseEnvEnum,
    BaseEnv,
    BaseConfig,
)
from config_patterns.logger import logger
from config_patterns.tests.mock import BaseMockTest


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


@dataclasses.dataclass
class ConfigTestCase:
    version: str

    @property
    def path_config(self) -> str:
        return str(dir_here.joinpath("data", self.version, "config.json"))

    @property
    def path_secret_config(self) -> str:
        return str(dir_here.joinpath("data", self.version, "secret_config.json"))

    @property
    def path_applied_data(self) -> str:
        return str(dir_here.joinpath("data", self.version, "applied_data.json"))

    @property
    def path_applied_secret_data(self) -> str:
        return str(dir_here.joinpath("data", self.version, "applied_secret_data.json"))

    @property
    def path_merged(self) -> str:
        return str(dir_here.joinpath("data", self.version, "merged.json"))

    @cached_property
    def config(self) -> Config:
        return Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            path_config=self.path_config,
            path_secret_config=self.path_secret_config,
        )

    @cached_property
    def applied_data(self) -> dict:
        return json.load(open(self.path_applied_data))

    @cached_property
    def applied_secret_data(self) -> dict:
        return json.load(open(self.path_applied_secret_data))

    @cached_property
    def merged_data(self) -> dict:
        return json.load(open(self.path_merged))


class TestConfig:
    def test(self):
        with pytest.raises(ValueError):
            Config.read(
                env_class=Env,
                env_enum_class=EnvEnum,
            )

        config_test_case = ConfigTestCase(version="v1")
        config = config_test_case.config
        assert config._applied_data == config_test_case.applied_data
        assert config._applied_secret_data == config_test_case.applied_secret_data
        assert config._merged == config_test_case.merged_data

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
            config_test_case = ConfigTestCase(version="v1")
            Config.read(
                env_class=Env,
                env_enum_class=EnvEnum,
                path_config=config_test_case.path_config,
                path_secret_config=config_test_case.path_secret_config,
            ).get_env(EnvEnum.dev.value)
            assert "please compare your config json file" in str(e)


class TestDeployment(BaseMockTest):
    use_mock: bool = True
    mock_list = [
        moto.mock_ssm,
        moto.mock_s3,
        moto.mock_sts,
    ]
    bsm: BotoSesManager = None

    @classmethod
    def setup_class_post_hook(cls):
        cls.bsm.s3_client.create_bucket(Bucket="my-bucket")
        cls.bsm.s3_client.create_bucket(Bucket="my-versioned-bucket")
        cls.bsm.s3_client.put_bucket_versioning(
            Bucket="my-versioned-bucket",
            VersioningConfiguration={"Status": "Enabled"},
        )
        context.attach_boto_session(cls.bsm.boto_ses)

    @property
    def bsm_collection(self) -> T.Dict[str, BotoSesManager]:
        return {
            ALL: self.bsm,
            EnvEnum.dev.value: self.bsm,
            EnvEnum.prod.value: self.bsm,
        }

    def _test_ssm_backend(self):
        # --- Parameter Store
        logger.ruler("First Deployment", char="*")
        config_v1 = ConfigTestCase(version="v1").config
        config_v1.delete(bsm=self.bsm, use_parameter_store=True)
        config_v1.deploy(bsm=self.bsm, parameter_with_encryption=True)

        logger.ruler("Read config from parameter store", char="*")
        config = Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            bsm=self.bsm,
            parameter_name=config_v1.parameter_name,
            parameter_with_encryption=True,
        )
        assert config.data == config_v1.data
        assert config.secret_data == config_v1.secret_data

        logger.ruler("Second Deployment, should do nothing", char="*")
        config.deploy(bsm=self.bsm_collection, parameter_with_encryption=True)

        logger.ruler("Third Deployment, should create a new version", char="*")
        config_v2 = ConfigTestCase(version="v2").config
        config_v2.deploy(bsm=self.bsm_collection, parameter_with_encryption=True)

        logger.ruler("Version one Deployment, should create a new version", char="*")
        config_v2 = ConfigTestCase(version="v2").config
        config_v2.deploy(bsm=self.bsm, parameter_with_encryption=True)

        logger.ruler("Delete Parameter", char="*")
        config.delete(bsm=self.bsm, use_parameter_store=True, include_history=False)

        logger.ruler("Read config from parameter store, should fail", char="*")
        with pytest.raises(exc.ParameterNotExists):
            Config.read(
                env_class=Env,
                env_enum_class=EnvEnum,
                bsm=self.bsm,
                parameter_name=config_v2.parameter_name,
                parameter_with_encryption=True,
            )

    def _test_s3_backend_version_not_enabled(self):
        s3folder_config = "s3://my-bucket/my-project/"
        s3dir_config = S3Path(s3folder_config)

        logger.ruler("First Deployment, deploy v1", char="*")
        config_v1 = ConfigTestCase(version="v1").config
        config_v1.delete(
            bsm=self.bsm,
            s3folder_config=s3folder_config,
            include_history=True,
            verbose=False,
        )
        config_v1.deploy(bsm=self.bsm, s3folder_config=s3folder_config)
        uri_list = [s3path.uri for s3path in sorted(s3dir_config.iter_objects())]
        assert uri_list == [
            "s3://my-bucket/my-project/my_project/my_project-000001.json",
            "s3://my-bucket/my-project/my_project/my_project-latest.json",
            "s3://my-bucket/my-project/my_project-dev/my_project-dev-000001.json",
            "s3://my-bucket/my-project/my_project-dev/my_project-dev-latest.json",
            "s3://my-bucket/my-project/my_project-prod/my_project-prod-000001.json",
            "s3://my-bucket/my-project/my_project-prod/my_project-prod-latest.json",
        ]

        logger.ruler("Read v1 config object from S3 Deployment", char="*")
        config = Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            bsm=self.bsm,
            parameter_name="my_project",
            s3folder_config=s3folder_config,
        )
        assert config.version == "1"

        logger.ruler("Second Deployment, should do nothing", char="*")
        config_v1.deploy(bsm=self.bsm, s3folder_config=s3folder_config)
        assert len(s3dir_config.iter_objects().all()) == 6

        logger.ruler("Third Deployment, deploy v2", char="*")
        config_v2 = ConfigTestCase(version="v2").config
        config_v2.deploy(bsm=self.bsm, s3folder_config=s3folder_config)
        s3path_list = s3dir_config.iter_objects().all()
        # *-000002.json should be created
        assert len(s3path_list) == 9
        for s3path in s3path_list:
            # the *.latest.json should have the version in the metadata
            if s3path.basename.endswith("latest.json"):
                assert s3path.metadata[KEY_CONFIG_VERSION] == "2"

        logger.ruler("Read v2 config object from S3 Deployment", char="*")
        config = Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            bsm=self.bsm,
            parameter_name="my_project-dev",
            s3folder_config=s3folder_config,
        )
        assert config.version == "2"

        logger.ruler("Delete latest version", char="*")
        config_v2.delete(bsm=self.bsm, s3folder_config=s3folder_config)
        s3path_list = s3dir_config.iter_objects().all()
        # only the *.latest.json should be deleted
        assert len(s3path_list) == 6

        logger.ruler("Read v2 config object from S3 Deployment, this time should fail", char="*")
        with pytest.raises(Exception):
            Config.read(
                env_class=Env,
                env_enum_class=EnvEnum,
                bsm=self.bsm,
                parameter_name="my_project-dev",
                s3folder_config=s3folder_config,
            )

        # the *.latest.json should be deleted
        s3path_latest_json_list = [
            s3path for s3path in s3path_list if s3path.basename.endswith("latest.json")
        ]
        assert len(s3path_latest_json_list) == 0

        logger.ruler("Fourth Deployment, should deploy v3", char="*")
        config_v3 = ConfigTestCase(version="v3").config
        config_v3.deploy(bsm=self.bsm, s3folder_config=s3folder_config)
        s3path_list = s3dir_config.iter_objects().all()
        # *-latest.json and *-000003.json should be created
        assert len(s3path_list) == 12
        for s3path in s3path_list:
            # the *.latest.json should have the version in the metadata
            if s3path.basename.endswith("latest.json"):
                assert s3path.metadata[KEY_CONFIG_VERSION] == "3"

        logger.ruler("Read v3 config object from S3 Deployment", char="*")
        config = Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            bsm=self.bsm,
            parameter_name="my_project-prod",
            s3folder_config=s3folder_config,
        )
        assert config.version == "3"

        logger.ruler("Delete latest versions", char="*")
        config_v3.delete(bsm=self.bsm, s3folder_config=s3folder_config)
        # only the *.latest.json should be deleted
        assert len(s3dir_config.iter_objects().all()) == 9

        logger.ruler("Delete historical versions", char="*")
        config_v3.delete(
            bsm=self.bsm, s3folder_config=s3folder_config, include_history=True
        )
        # all *.json should be deleted
        assert len(s3dir_config.iter_objects().all()) == 0

        logger.ruler("Read config object from S3 Deployment, this should fail", char="*")
        with pytest.raises(exc.S3ObjectNotExist):
            _ = Config.read(
                env_class=Env,
                env_enum_class=EnvEnum,
                bsm=self.bsm,
                parameter_name="my_project-prod",
                s3folder_config=s3folder_config,
            )

        with pytest.raises(ValueError):
            # missing arguments
            config_v3.delete(bsm=self.bsm)

        with pytest.raises(ValueError):
            # argument type error
            config_v3.deploy(bsm=self.bsm, parameter_with_encryption="YES")

        with pytest.raises(ValueError):
            # missing arguments
            config_v3.deploy(bsm=self.bsm)

    def _test_s3_backend_version_enabled(self):
        s3folder_config = "s3://my-versioned-bucket/my-project/"
        s3dir_config = S3Path(s3folder_config)

        logger.ruler("First Deployment, deploy v1", char="*")
        config_v1 = ConfigTestCase(version="v1").config
        config_v1.delete(
            bsm=self.bsm,
            s3folder_config=s3folder_config,
            include_history=True,
            verbose=False,
        )
        config_v1.deploy(bsm=self.bsm, s3folder_config=s3folder_config)
        uri_list = [s3path.uri for s3path in sorted(s3dir_config.iter_objects())]
        assert uri_list == [
            "s3://my-versioned-bucket/my-project/my_project-dev.json",
            "s3://my-versioned-bucket/my-project/my_project-prod.json",
            "s3://my-versioned-bucket/my-project/my_project.json",
        ]
        v1 = S3Path("s3://my-versioned-bucket/my-project/my_project.json").version_id

        logger.ruler("Read v1 config object from S3 Deployment", char="*")
        config = Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            bsm=self.bsm,
            parameter_name="my_project",
            s3folder_config=s3folder_config,
        )
        assert config.version == v1

        logger.ruler("Second Deployment, should do nothing", char="*")
        config_v1.deploy(bsm=self.bsm, s3folder_config=s3folder_config)
        s3path_list = s3dir_config.iter_objects().all()
        assert len(s3path_list) == 3
        # all objects should have only one version
        for s3path in s3path_list:
            assert len(s3path.list_object_versions().all()) == 1
        assert S3Path("s3://my-versioned-bucket/my-project/my_project.json").version_id == v1

        logger.ruler("Third Deployment, deploy v2", char="*")
        config_v2 = ConfigTestCase(version="v2").config
        config_v2.deploy(bsm=self.bsm, s3folder_config=s3folder_config)
        s3path_list = s3dir_config.iter_objects().all()
        assert len(s3path_list) == 3
        # all objects should have two versions
        for s3path in s3path_list:
            assert len(s3path.list_object_versions().all()) == 2
        # v1 should be different from v2
        v2 = S3Path("s3://my-versioned-bucket/my-project/my_project.json").version_id

        logger.ruler("Read v2 config object from S3 Deployment", char="*")
        config = Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            bsm=self.bsm,
            parameter_name="my_project",
            s3folder_config=s3folder_config,
        )
        assert config.version == v2

        logger.ruler("Delete latest version", char="*")
        config_v2.delete(bsm=self.bsm, s3folder_config=s3folder_config)
        # just put a delete marker on top of v2, s3 object is "not exists"
        s3path_list = s3dir_config.iter_objects().all()
        assert len(s3path_list) == 0

        # now it should have 3 version, v1, v2 and the delete marker
        assert len(S3Path("s3://my-versioned-bucket/my-project/my_project.json").list_object_versions().all()) == 3

        logger.ruler("Read v2 config object from S3 Deployment, this time should fail", char="*")
        with pytest.raises(Exception):
            config = Config.read(
                env_class=Env,
                env_enum_class=EnvEnum,
                bsm=self.bsm,
                parameter_name="my_project",
                s3folder_config=s3folder_config,
            )

        logger.ruler("Fourth Deployment, should deploy v3", char="*")
        config_v3 = ConfigTestCase(version="v3").config
        config_v3.deploy(bsm=self.bsm, s3folder_config=s3folder_config)
        s3path_list = s3dir_config.iter_objects().all()
        assert len(s3path_list) == 3

        for s3path in s3path_list:
            assert len(s3path.list_object_versions().all()) == 4

        logger.ruler("Read v3 config object from S3 Deployment", char="*")
        config = Config.read(
            env_class=Env,
            env_enum_class=EnvEnum,
            bsm=self.bsm,
            parameter_name="my_project",
            s3folder_config=s3folder_config,
        )
        v3 = S3Path("s3://my-versioned-bucket/my-project/my_project.json").version_id
        assert config.version == v3

        logger.ruler("Delete latest versions", char="*")
        config_v3.delete(bsm=self.bsm, s3folder_config=s3folder_config)
        # just put a delete marker on top of v3, s3 object is "not exists"
        assert len(s3dir_config.iter_objects().all()) == 0
        # now it should have 5 version, v1, v2 and the v2 delete marker, v3 and the v3 delete marker
        assert len(S3Path("s3://my-versioned-bucket/my-project/my_project.json").list_object_versions().all()) == 5

        logger.ruler("Delete historical versions", char="*")
        config_v3.delete(
            bsm=self.bsm, s3folder_config=s3folder_config, include_history=True
        )
        # all *.json and historical version should be deleted
        assert len(s3dir_config.iter_objects().all()) == 0
        assert len(S3Path("s3://my-versioned-bucket/my-project/my_project.json").list_object_versions().all()) == 0

        logger.ruler("Read config object from S3 Deployment, this should fail", char="*")
        with pytest.raises(exc.S3ObjectNotExist):
            _ = Config.read(
                env_class=Env,
                env_enum_class=EnvEnum,
                bsm=self.bsm,
                parameter_name="my_project-prod",
                s3folder_config=s3folder_config,
            )

    def test(self):
        print("")
        with logger.disabled(
            disable=True,
            # disable=False,
        ):
            self._test_ssm_backend()
            self._test_s3_backend_version_not_enabled()
            self._test_s3_backend_version_enabled()

if __name__ == "__main__":
    from config_patterns.tests import run_cov_test

    run_cov_test(
        __file__, "config_patterns.patterns.multi_env_json.impl", preview=False
    )

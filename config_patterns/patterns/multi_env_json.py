# -*- coding: utf-8 -*-

import typing as T
import copy
import enum
import string
import dataclasses
from pathlib import Path

#
try:
    import boto3
    import boto_session_manager
except ImportError:  # pragma: no cover
    pass

#
try:
    import pysecret
    import aws_console_url

    from ..aws.ssm import deploy_parameter
    from ..aws.s3 import deploy_config
except ImportError:  # pragma: no cover
    pass


from ..jsonutils import json_loads
from ..compat import cached_property
from ..vendor.strutils import camel2under, slugify


def validate_project_name(project_name: str):
    if project_name[0] not in string.ascii_lowercase:
        raise ValueError("first letter of project_name has to be a-z!")
    if project_name[-1] not in (string.ascii_lowercase + string.digits):
        raise ValueError("last letter of project_name has to be a-z, 0-9!")
    if len(set(project_name).difference(string.ascii_lowercase + string.digits + "_-")):
        raise ValueError("project_name can only has a-z, 0-9, - or _!")


def validate_env_name(env_name: str):
    if env_name[0] not in string.ascii_lowercase:
        raise ValueError("first letter of env_name has to be a-z!")
    if len(set(env_name).difference(string.ascii_lowercase + string.digits)):
        raise ValueError("env_name can only has a-z, 0-9")


class BaseEnvEnum(str, enum.Enum):
    """
    Base per environment enumeration base class.

    an environment name is a string that is full lowercase, can include
    letters and digits, start with letter, no delimiter.
    Valid examples are: dev, test, prod, stage1, stage2,
    Invalid examples are: my_dev, 1dev
    """

    @classmethod
    def ensure_str(cls, value: T.Union[str, "BaseEnvEnum"]) -> str:
        if isinstance(value, cls):
            return value.value
        else:
            return value


@dataclasses.dataclass
class BaseEnv:
    """
    Per environment config data.

    :param project_name: a project name is a string that is full lowercase,
        can include letters and digits, start with letter, _ or - delimiter only
        cannot start or end with delimiter.
        Valid examples are : my_project, my-project, my-1-project
        Invalid examples are: my project, 1-my-project, -my-project, my-project-
    :param env_name: an environment name is a string that is full lowercase,
        can include letters and digits, start with letter, no delimiter.
        Valid examples are: dev, test, prod, stage1, stage2
        Invalid examples are: my_dev, 1dev
    """

    project_name: T.Optional[str] = dataclasses.field(default=None)
    env_name: T.Optional[str] = dataclasses.field(default=None)

    def _validate(self):
        """
        Validate input arguments.
        """
        if self.project_name is not None:
            validate_project_name(self.project_name)
        if self.env_name is not None:
            validate_env_name(self.env_name)

    def __user_post_init__(self):
        """
        A placeholder post init function for user.
        """
        pass

    def __post_init__(self):
        """
        User should not overwrite this method. You can use __user_post_init__
        for any post init logics.
        """
        self._validate()
        self.__user_post_init__()

    @cached_property
    def project_name_slug(self) -> str:
        """
        Example: "my-project"
        """
        return slugify(self.project_name, delim="-")

    @cached_property
    def project_name_snake(self) -> str:
        """
        Example: "my_project"
        """
        return slugify(self.project_name, delim="_")

    @cached_property
    def prefix_name_slug(self) -> str:
        """
        Example: "my-project-dev"
        """
        return f"{self.project_name_slug}-{self.env_name}"

    @cached_property
    def prefix_name_snake(self) -> str:
        """
        Example: "my_project-dev"
        """
        return f"{self.project_name_snake}-{self.env_name}"

    @cached_property
    def parameter_name(self) -> str:
        return self.prefix_name_snake


@dataclasses.dataclass
class BaseConfig:
    """
    The base class for multi-environment config object.

    :param data: Nonsensitive config data.
    :param secret_data: Sensitive config data.

    Example data and secret_data::

        >>> {
        ...     "shared": {
        ...         "project_name": "my_project", # has to have a key called ``project_name``
        ...         "key": "value",
        ...         ...
        ...     },
        ...     "envs": {
        ...         "dev": {
        ...             "key": "value",
        ...             ...
        ...         },
        ...         "int": {
        ...             "key": "value",
        ...             ...
        ...         },
        ...         "prod": {
        ...             "key": "value",
        ...             ...
        ...         },
        ...         ...
        ...     }
        ... }
    """

    data: dict = dataclasses.field()
    secret_data: dict = dataclasses.field()

    Env: T.Type[BaseEnv] = dataclasses.field()
    EnvEnum: T.Type[BaseEnvEnum] = dataclasses.field()

    def _validate(self):
        """
        Validate input arguments.
        """
        validate_project_name(self.project_name)
        for env_name in self.data["envs"]:
            validate_env_name(env_name)

    def __user_post_init__(self):
        """
        A placeholder post init function for user.
        """
        pass

    def __post_init__(self):
        """
        User should not overwrite this method. You can use __user_post_init__
        for any post init logics.
        """
        self._validate()
        self.__user_post_init__()

    @cached_property
    def project_name(self) -> str:
        return self.data["shared"]["project_name"]

    @cached_property
    def project_name_slug(self) -> str:
        return slugify(self.project_name, delim="-")

    @cached_property
    def project_name_snake(self) -> str:
        return slugify(self.project_name, delim="_")

    def get_env(self, env_name: T.Union[str, BaseEnvEnum]):
        env_name = BaseEnvEnum.ensure_str(env_name)
        data = dict()
        data.update(copy.deepcopy(self.data["shared"]))
        data.update(copy.deepcopy(self.secret_data["shared"]))
        data.update(copy.deepcopy(self.data["envs"][env_name]))
        data.update(copy.deepcopy(self.secret_data["envs"][env_name]))
        data["env_name"] = env_name
        return self.Env(**data)

    @classmethod
    def get_current_env(cls) -> str:
        raise NotImplementedError(
            "You have to implement this method to detect what environment "
            "you should use. It should be a class method that take no argument "
            "and returns a string. Usually you could use environment variable to detect "
            "whether you are on your local laptop, CI runtime, remote machine. "
            "Also you can use subprocess to call git CLI to check your current branch."
        )

    @cached_property
    def env(self) -> BaseEnv:
        """
        Access the current :class:`Env` object.
        """
        return self.get_env(env_name=self.get_current_env())

    @classmethod
    def read(
        cls,
        env_class: T.Type[BaseEnv],
        env_enum_class: T.Type[BaseEnvEnum],
        path_config: T.Optional[str] = None,
        path_secret_config: T.Optional[str] = None,
        parameter_name: T.Optional[str] = None,
        parameter_with_encryption: T.Optional[bool] = None,
        s3path_config: T.Optional[str] = None,
    ):
        """
        Create and initialize the config object from configuration store.
        Currently, it supports:

        1. read from local config files.
        2. read from AWS Parameter Store.
        3. read from AWS S3.

        :param env_class: the per environment config dataclass object.
        :param env_enum_class: the environment enumeration class.
        :param path_config: local file path to the non-sensitive config file.
        :param path_secret_config: local file path to the sensitive config file.
        :param parameter_name: the AWS Parameter name.
        :param parameter_with_encryption: is AWS Parameter turned on encryption?
        :param s3path_config: the s3 uri to the config file.
        :return:
        """
        if (path_config is not None) and (path_secret_config is not None):
            data = json_loads(Path(path_config).read_text())
            secret_data = json_loads(Path(path_secret_config).read_text())
            return cls(
                data=data,
                secret_data=secret_data,
                Env=env_class,
                EnvEnum=env_enum_class,
            )
        elif (parameter_name is not None) and (
            parameter_with_encryption is not None
        ):  # pragma: no cover
            aws_secret = pysecret.AWSSecret(boto_session=boto3.session.Session())
            parameter_data = aws_secret.get_parameter_data(
                name=parameter_name,
                with_encryption=parameter_with_encryption,
            )
            return cls(
                data=parameter_data["data"],
                secret_data=parameter_data["secret_data"],
                Env=env_class,
                EnvEnum=env_enum_class,
            )
        elif s3path_config is not None:  # pragma: no cover
            s3_client = boto3.client("s3")
            parts = s3path_config.split("/", 3)
            bucket = parts[2]
            key = parts[3]
            config_data = json_loads(
                s3_client.get_object(Bucket=bucket, Key=key)["Body"]
                .read()
                .decode("utf-8")
            )
            return cls(
                data=config_data["data"],
                secret_data=config_data["secret_data"],
                Env=env_class,
                EnvEnum=env_enum_class,
            )
        else:
            raise ValueError(
                "The arguments has to meet one of these criteria:\n"
                "1. set both ``path_config`` and ``path_secret_config`` to indicate that "
                "you want to read config from local config json file.\n"
                "2. set both ``parameter_name`` and ``parameter_with_encryption`` "
                "to indicate that you want to read from AWS Parameter Store.\n"
                "3. set ``s3path_config`` similar to s3://my-bucket/my-project/dev.json "
                "to indicate that you want to read from AWS S3.\n"
            )

    def _prepare_deploy(
        self,
    ) -> T.List[T.Tuple[str, dict, str, str]]:  # pragma: no cover
        """
        split the consolidated config into per environment config.

        :return a list of tuple, each tuple has four item: 1. parameter_name,
            2. parameter_data, 3. project_name, 4. env_name.
        """
        parameter_list: T.List[T.Tuple[str, dict, str, str]] = list()
        parameter_name = self.project_name_slug
        parameter_data = {"data": self.data, "secret_data": self.secret_data}
        parameter_list.append(
            (parameter_name, parameter_data, self.project_name, "all")
        )

        for env_name in self.EnvEnum:
            env_name = self.EnvEnum.ensure_str(env_name)
            env = self.get_env(env_name)
            parameter_name = env.parameter_name
            parameter_data = {
                "data": {
                    "shared": self.data["shared"],
                    "envs": {env.env_name: self.data["envs"][env.env_name]},
                },
                "secret_data": {
                    "shared": self.secret_data["shared"],
                    "envs": {env.env_name: self.secret_data["envs"][env.env_name]},
                },
            }
            parameter_list.append(
                (parameter_name, parameter_data, env.project_name, env.env_name)
            )

        return parameter_list

    def deploy(
        self,
        bsm: T.Optional["boto_session_manager.BotoSesManager"] = None,
        parameter_with_encryption: T.Optional[bool] = None,
        s3dir_config: T.Optional[str] = None,
    ):  # pragma: no cover
        """
        Deploy the project config of all environments to configuration store.
        Currently, it supports:

        1. deploy to AWS Parameter Store
        2. deploy to AWS S3

        :param bsm:
        :param parameter_with_encryption:
        :param s3dir_config:

        Note:

            this function should ONLY run from the project admin's trusted
            laptop.
        """
        if (bsm is not None) and (parameter_with_encryption is not None):
            # validate arguments
            if not (
                (parameter_with_encryption is True)
                or (parameter_with_encryption is False)
            ):
                raise ValueError
            print("deploy parameter store for all environment")
            parameter_list = self._prepare_deploy()
            for (
                parameter_name,
                parameter_data,
                project_name,
                env_name,
            ) in parameter_list:
                deploy_parameter(
                    bsm=bsm,
                    parameter_name=parameter_name,
                    parameter_data=parameter_data,
                    parameter_with_encryption=parameter_with_encryption,
                    tags=dict(
                        ProjectName=project_name,
                        EnvName=env_name,
                    ),
                )
        elif (bsm is not None) and (s3dir_config is not None):
            if not s3dir_config.endswith("/"):
                raise ValueError(
                    "s3dir_config has to be a folder and end with /, "
                    "a valid example: s3://my-bucket/my-project/."
                )
            parameter_list = self._prepare_deploy()
            deploy_config(
                bsm=bsm,
                s3path_config=f"{s3dir_config}all.json",
                config_data=parameter_list[0][1],
                tags=dict(
                    ProjectName=parameter_list[0][2],
                    EnvName=parameter_list[0][3],
                ),
            )

            for _, parameter_data, project_name, env_name in parameter_list[1:]:
                deploy_config(
                    bsm=bsm,
                    s3path_config=f"{s3dir_config}{env_name}.json",
                    config_data=parameter_data,
                    tags=dict(
                        ProjectName=project_name,
                        EnvName=env_name,
                    ),
                )
        else:
            raise ValueError(
                "The arguments has to meet one of these criteria:\n"
                "1. set ``parameter_with_encryption`` to True or False to indicate that "
                "you want to deploy to AWS Parameter Store.\n"
                "2. set ``s3dir_config`` similar to s3://my-bucket/my-project/ "
                "to indicate that you want to deploy to S3."
            )

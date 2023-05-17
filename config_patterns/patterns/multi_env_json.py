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

    from ..aws.ssm import deploy_parameter, delete_parameter
    from ..aws.s3 import deploy_config, delete_config, S3Object
except ImportError:  # pragma: no cover
    pass

from ..logger import logger
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


def normalize_parameter_name(param_name: str) -> str:
    """
    AWS has limitation that the name cannot be prefixed with "aws" or "ssm",
    so this method will automatically add prepend character to the name.

    Ref:

    - AWS Parameter Name Limitation: https://docs.aws.amazon.com/cli/latest/reference/ssm/put-parameter.html#options
    """
    if param_name.startswith("aws") or param_name.startswith("ssm"):
        return f"p-{param_name}"
    else:
        return param_name


SHARED = "_shared"


def set_shared_value(
    path: str,
    value: T.Any,
    data: T.Union[list, dict],
):
    """
    Set shared value to all items in a list or dict.
    """
    parts = path.split(".")
    if len(parts) == 1:
        if isinstance(data, dict):
            data.setdefault(parts[0], value)
        elif isinstance(data, list):
            for item in data:
                item.setdefault(parts[0], value)
        else:  # pragma: no cover
            raise NotImplementedError
        return
    key = parts[0]
    if key == "*":
        for k, v in data.items():
            if k != SHARED:
                set_shared_value(
                    path=".".join(parts[1:]),
                    value=value,
                    data=v,
                )
    else:
        if isinstance(data, dict):
            set_shared_value(
                path=".".join(parts[1:]),
                value=value,
                data=data[key],
            )
        elif isinstance(data, list):
            for item in data:
                set_shared_value(
                    path=".".join(parts[1:]),
                    value=value,
                    data=item[key],
                )
        else:  # pragma: no cover
            raise NotImplementedError


def apply_shared_value(data: dict):
    # implement recursion pattern
    for key, value in data.items():
        if key == SHARED:
            continue
        if isinstance(value, dict):
            apply_shared_value(value)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    apply_shared_value(item)

    has_shared = SHARED in data
    if has_shared is False:
        return

    shared_data = data.pop(SHARED)
    for path, value in shared_data.items():
        set_shared_value(path=path, value=value, data=data)


def merge_key_value(data1: dict, data2: dict):
    data1 = copy.deepcopy(data1)
    data2 = copy.deepcopy(data2)

    difference = data2.keys() - data1.keys()
    intersection = data1.keys() & data2.keys()

    for key in difference:
        data1[key] = data2[key]

    for key in intersection:
        value1, value2 = data1[key], data2[key]
        if isinstance(value1, dict) and isinstance(value2, dict):
            data1[key] = merge_key_value(value1, value2)
        elif isinstance(value1, list) and isinstance(value2, list):
            if len(value1) != len(value2):
                raise ValueError(f"list length mismatch: key = {key!r}")
            value = list()
            for item1, item2 in zip(value1, value2):
                if isinstance(item1, dict) and isinstance(item2, dict):
                    value.append(merge_key_value(item1, item2))
                else:
                    raise ValueError
            data1[key] = value
        else:
            raise TypeError(
                f"type of data1[{key!r}] and type of data2[{key!r}] "
                f"has to be both dict or list of dict to merge! "
                f"they are {type(value1)} and {type(value2)}."
            )

    return data1


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

    @classmethod
    def from_dict(cls, data: dict):  # pragma: no cover
        """
        Create an instance from a dict.
        """
        raise NotImplementedError(
            "Implement this method create an instance of "
            "env config. For example:\n"
            "@classmethod\n"
            "def from_dict(cls, data: dict):\n"
            "    return cls(**data)\n"
        )

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
        """
        Return the per-environment AWS SSM Parameter name.
        Usually, the naming convention is "${project_name}-${env_name}"".

        Example: "my_project-dev"
        """
        return normalize_parameter_name(self.prefix_name_snake)


@dataclasses.dataclass
class ConfigDeployment:
    """
    Represent a config deployment on remote data store.

    It has the following methods:

    - :meth:`~ConfigDeployment.deploy_to_ssm_parameter`
    - :meth:`~ConfigDeployment.deploy_to_s3`
    - :meth:`~ConfigDeployment.delete_from_ssm_parameter`
    - :meth:`~ConfigDeployment.delete_from_s3`

    :param parameter_name: the logic name of this deployment
    :param parameter_data: the config data in python dict
    :param project_name: project name
    :param env_name: environment name
    :param deployment: the deployment object, it can be either AWS Parameter or S3 Object
    :param deletion: whether there is a deletion happened
    """

    parameter_name: str = dataclasses.field()
    parameter_data: dict = dataclasses.field()
    project_name: str = dataclasses.field()
    env_name: str = dataclasses.field()
    deployment: T.Optional[T.Union["pysecret.Parameter", S3Object]] = dataclasses.field(
        default=None
    )
    deletion: T.Optional[bool] = dataclasses.field(default=None)

    @property
    def parameter_name_for_arn(self) -> str:
        """
        Return the parameter name for ARN. The parameter name could have
        a leading "/", in this case, we should strip it out.
        """
        if self.parameter_name.startswith("/"):  # pragma: no cover
            return self.parameter_name[1:]
        else:
            return self.parameter_name

    def deploy_to_ssm_parameter(
        self,
        bsm: "boto_session_manager.BotoSesManager",
        parameter_with_encryption: bool,
        tags: T.Optional[T.Dict[str, str]] = None,
        verbose: bool = True,
    ):
        """
        Deploy config to AWS SSM Parameter Store.
        """
        if tags is None:
            tags = dict(
                ProjectName=self.project_name,
                EnvName=self.env_name,
            )
        with logger.disabled(
            disable=not verbose,
        ):
            self.deployment = deploy_parameter(
                bsm=bsm,
                parameter_name=self.parameter_name,
                parameter_data=self.parameter_data,
                parameter_with_encryption=parameter_with_encryption,
                tags=tags,
            )
            return self.deployment

    def deploy_to_s3(
        self,
        bsm: "boto_session_manager.BotoSesManager",
        s3dir_config: str,
        tags: T.Optional[T.Dict[str, str]] = None,
        verbose: bool = True,
    ):
        """
        Deploy config to AWS S3.
        """
        if tags is None:
            tags = dict(
                ProjectName=self.project_name,
                EnvName=self.env_name,
            )
        with logger.disabled(
            disable=not verbose,
        ):
            self.deployment = deploy_config(
                bsm=bsm,
                s3path_config=f"{s3dir_config}{self.parameter_name_for_arn}.json",
                config_data=self.parameter_data,
                tags=tags,
            )
            return self.deployment

    def delete_from_ssm_parameter(
        self,
        bsm: "boto_session_manager.BotoSesManager",
        verbose: bool = True,
    ):
        """
        Delete config from AWS SSM Parameter Store.
        """
        with logger.disabled(
            disable=not verbose,
        ):
            self.deletion = delete_parameter(
                bsm=bsm,
                parameter_name=self.parameter_name,
            )
            return self.deletion

    def delete_from_s3(
        self,
        bsm: "boto_session_manager.BotoSesManager",
        s3dir_config: str,
        verbose: bool = True,
    ):
        """
        Delete config from AWS S3.
        """
        with logger.disabled(
            disable=not verbose,
        ):
            s3_uri = f"{s3dir_config}{self.parameter_name_for_arn}.json"
            self.deletion = delete_config(
                bsm=bsm,
                s3path_config=s3_uri,
            )
            return self.deletion


@dataclasses.dataclass
class BaseConfig:
    """
    The base class for multi-environment config object.

    :param data: Nonsensitive config data.
    :param secret_data: Sensitive config data.

    Example data and secret_data::

        >>> {
        ...     "_shared": {
        ...         "project_name": "my_project", # has to have a key called ``project_name``
        ...         "key": "value",
        ...         ...
        ...     },
        ...     "dev": {
        ...         "key": "value",
        ...         ...
        ...     },
        ...     "int": {
        ...         "key": "value",
        ...         ...
        ...     },
        ...     "prod": {
        ...         "key": "value",
        ...         ...
        ...     },
        ...     ...
        ... }
    """

    data: dict = dataclasses.field()
    secret_data: dict = dataclasses.field()

    Env: T.Type[BaseEnv] = dataclasses.field()
    EnvEnum: T.Type[BaseEnvEnum] = dataclasses.field()

    _merged_data: dict = dataclasses.field(init=False)
    _merged_secret_data: dict = dataclasses.field(init=False)
    _merged: dict = dataclasses.field(init=False)

    def _validate(self):
        """
        Validate input arguments.
        """
        validate_project_name(self.project_name)
        for env_name in self.data:
            if env_name != "_shared":
                validate_env_name(env_name)

    def _apply_shared(self):
        self._merged_data = copy.deepcopy(self.data)
        self._merged_secret_data = copy.deepcopy(self.secret_data)
        apply_shared_value(self._merged_data)
        apply_shared_value(self._merged_secret_data)
        self._merged = merge_key_value(self._merged_data, self._merged_secret_data)

    def __user_post_init__(self):
        """
        A placeholder post init function for user.
        """

    def __post_init__(self):
        """
        User should not overwrite this method. You can use __user_post_init__
        for any post init logics.
        """
        self._validate()
        self._apply_shared()
        self.__user_post_init__()

    @cached_property
    def project_name(self) -> str:
        return self.data["_shared"]["*.project_name"]

    @cached_property
    def project_name_slug(self) -> str:
        return slugify(self.project_name, delim="-")

    @cached_property
    def project_name_snake(self) -> str:
        return slugify(self.project_name, delim="_")

    @cached_property
    def parameter_name(self) -> str:
        """
        Return the all-environment AWS SSM Parameter name.
        Usually, the naming convention is "${project_name}".

        Example: "my_project-dev"
        """
        return normalize_parameter_name(self.project_name_snake)

    # don't put type hint for return value, it should return a
    # user defined subclass, which is impossible to predict.
    def get_env(self, env_name: T.Union[str, BaseEnvEnum]):
        env_name = BaseEnvEnum.ensure_str(env_name)
        data = copy.deepcopy(self._merged[env_name])
        data["env_name"] = env_name
        try:
            return self.Env.from_dict(data)
        except TypeError as e:
            if "got an unexpected keyword argument" in str(e):
                raise TypeError(
                    f"{e}, please compare your config json file "
                    f"to your config object definition!"
                )
            else:  # pragma: no cover
                raise e

    @classmethod
    def get_current_env(cls) -> str:  # pragma: no cover
        """
        An abstract method that can figure out what is the environment this config
        should deal with. For example, you can define the git feature branch
        will become the dev env; the master branch will become the int env;
        the release branch will become prod env;
        """
        raise NotImplementedError(
            "You have to implement this method to detect what environment "
            "you should use. It should be a class method that take no argument "
            "and returns a string. Usually you could use environment variable to detect "
            "whether you are on your local laptop, CI runtime, remote machine. "
            "Also you can use subprocess to call git CLI to check your current branch."
        )

    # don't put type hint for return value, it should return a
    # user defined subclass, which is impossible to predict.
    @cached_property
    def env(self):  # pragma: no cover
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
        bsm: T.Optional["boto_session_manager.BotoSesManager"] = None,
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
            parameter = pysecret.Parameter.load(
                ssm_client=bsm.ssm_client,
                name=parameter_name,
                with_decryption=parameter_with_encryption,
            )
            parameter_data = parameter.json_dict
            return cls(
                data=parameter_data["data"],
                secret_data=parameter_data["secret_data"],
                Env=env_class,
                EnvEnum=env_enum_class,
            )
        elif s3path_config is not None:  # pragma: no cover
            parts = s3path_config.split("/", 3)
            bucket = parts[2]
            key = parts[3]
            config_data = json_loads(
                bsm.s3_client.get_object(Bucket=bucket, Key=key)["Body"]
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

    def prepare_deploy(self) -> T.List[ConfigDeployment]:
        """
        split the consolidated config into per environment config.

        :return a list of deployment.
        """
        deployment_list: T.List[ConfigDeployment] = list()

        # manually add all env parameter, the name is project_name only
        # without env_name
        parameter_name = self.parameter_name
        parameter_data = {"data": self.data, "secret_data": self.secret_data}
        deployment_list.append(
            ConfigDeployment(
                parameter_name=parameter_name,
                parameter_data=parameter_data,
                project_name=self.project_name,
                env_name="all",
            )
        )

        # add per env parameter
        for env_name in self.EnvEnum:
            env_name = self.EnvEnum.ensure_str(env_name)
            env = self.get_env(env_name)
            parameter_name = env.parameter_name

            parameter_data = {
                "data": {
                    "shared": {
                        k: v
                        for k, v in self.data.get("_shared", {}).items()
                        if k.startswith("*") or k.startswith(f"{env.env_name}.")
                    },
                    "envs": {env.env_name: self.data[env.env_name]},
                },
                "secret_data": {
                    "shared": {
                        k: v
                        for k, v in self.secret_data.get("_shared", {}).items()
                        if k.startswith("*") or k.startswith(f"{env.env_name}.")
                    },
                    "envs": {env.env_name: self.secret_data[env.env_name]},
                },
            }
            deployment_list.append(
                ConfigDeployment(
                    parameter_name=parameter_name,
                    parameter_data=parameter_data,
                    project_name=env.project_name,
                    env_name=env.env_name,
                )
            )

        return deployment_list

    def deploy(
        self,
        bsm: "boto_session_manager.BotoSesManager",
        parameter_with_encryption: T.Optional[bool] = None,
        s3dir_config: T.Optional[str] = None,
        tags: T.Optional[T.Dict[str, str]] = None,
        verbose: bool = True,
    ) -> T.List[ConfigDeployment]:
        """
        Deploy the project config of all environments to configuration store.
        Currently, it supports:

        1. deploy to AWS Parameter Store
        2. deploy to AWS S3

        Note:

            this function should ONLY run from the project admin's trusted laptop.

        :param bsm:
        :param parameter_with_encryption:
        :param s3dir_config:
        :param tags:
        :param verbose:

        :return: a list of :class:`ConfigDeployment`.
        """
        if parameter_with_encryption is not None:
            # validate arguments
            if not (
                (parameter_with_encryption is True)
                or (parameter_with_encryption is False)
            ):
                raise ValueError("parameter_with_encryption has to be True or False!")
            deployment_list = self.prepare_deploy()
            for deployment in deployment_list:
                deployment.deploy_to_ssm_parameter(
                    bsm=bsm,
                    parameter_with_encryption=parameter_with_encryption,
                    tags=tags,
                    verbose=verbose,
                )
            return deployment_list
        elif s3dir_config is not None:
            deployment_list = self.prepare_deploy()
            for deployment in deployment_list:
                deployment.deploy_to_s3(
                    bsm=bsm,
                    s3dir_config=s3dir_config,
                    tags=tags,
                    verbose=verbose,
                )
            return deployment_list
        else:
            raise ValueError(
                "The arguments has to meet one of these criteria:\n"
                "1. set ``parameter_with_encryption`` to True or False to indicate that "
                "you want to deploy to AWS Parameter Store.\n"
                "2. set ``s3dir_config`` similar to s3://my-bucket/my-project/ "
                "to indicate that you want to deploy to S3."
            )

    def delete(
        self,
        bsm: "boto_session_manager.BotoSesManager",
        use_parameter_store: T.Optional[bool] = None,
        s3dir_config: T.Optional[str] = None,
        verbose: bool = True,
    ):
        """
        Delete the all project config of all environments from configuration store.

        Currently, it supports:

        1. delete from AWS Parameter Store
        2. delete from AWS S3

        :param bsm:
        :param use_parameter_store:
        :param s3dir_config:
        :param verbose:

        :return: a list of :class:`ConfigDeployment`.

        Note:

            this function should ONLY run from the project admin's trusted laptop.
        """
        if (bsm is not None) and (use_parameter_store is True):
            deployment_list = self.prepare_deploy()
            for deployment in deployment_list:
                deployment.delete_from_ssm_parameter(
                    bsm=bsm,
                    verbose=verbose,
                )
            return deployment_list
        elif (bsm is not None) and (s3dir_config is not None):
            deployment_list = self.prepare_deploy()
            for deployment in deployment_list:
                deployment.delete_from_s3(
                    bsm=bsm,
                    s3dir_config=s3dir_config,
                    verbose=verbose,
                )
            return deployment_list
        else:
            raise ValueError(
                "The arguments has to meet one of these criteria:\n"
                "1. set ``use_parameter_store`` to True to indicate that "
                "you want to delete config from AWS Parameter Store.\n"
                "2. set ``s3dir_config`` similar to s3://my-bucket/my-project/ "
                "to indicate that you want to delete config file from S3."
            )

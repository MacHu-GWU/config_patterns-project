# -*- coding: utf-8 -*-

import typing as T
import copy
import string
import dataclasses
from pathlib import Path

# import optional dependencies
try:
    import boto3
    import boto_session_manager
except ImportError:  # pragma: no cover
    pass

try:
    import pysecret
    from s3pathlib import S3Path

    from ...aws.ssm import deploy_parameter, delete_parameter
    from ...aws.s3 import (
        get_bucket_version_status,
        read_config,
        deploy_config,
        delete_config,
        S3Object,
    )
except ImportError:  # pragma: no cover
    pass

from ... import exc
from ...logger import logger
from ...jsonutils import json_loads
from ...compat import cached_property
from ...utils import sha256_of_config_data
from ...vendor.strutils import slugify
from ...vendor.better_enum import BetterStrEnum
from ..hierarchy.api import apply_shared_value
from ..merge_key_value.api import merge_key_value


ALL = "all"


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


class BaseEnvEnum(BetterStrEnum):
    """
    Base per environment enumeration base class.

    an environment name is a string that is full lowercase, can include
    letters and digits, start with letter, no delimiter.
    Valid examples are: dev, test, prod, stage1, stage2,
    Invalid examples are: my_dev, 1dev
    """


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
            tags = {}

        tags.update(
            {
                "config_pattern:project_name": self.project_name,
                "config_pattern:env_name": self.env_name,
                "config_pattern:config_sha256": sha256_of_config_data(
                    self.parameter_data
                ),
            }
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
        s3folder_config: str,
        tags: T.Optional[T.Dict[str, str]] = None,
        verbose: bool = True,
    ):
        """
        Deploy config to AWS S3.
        """
        if tags is None:
            tags = {}

        tags.update(
            {
                "config_pattern:project_name": self.project_name,
                "config_pattern:env_name": self.env_name,
            }
        )

        with logger.disabled(
            disable=not verbose,
        ):
            self.deployment = deploy_config(
                bsm=bsm,
                s3folder_config=S3Path(s3folder_config).to_dir().uri,
                parameter_name=self.parameter_name_for_arn,
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
        s3folder_config: str,
        include_history: bool = False,
        verbose: bool = True,
    ):
        """
        Delete config from AWS S3.
        """
        with logger.disabled(
            disable=not verbose,
        ):
            self.deletion = delete_config(
                bsm=bsm,
                s3folder_config=S3Path(s3folder_config).to_dir().uri,
                parameter_name=self.parameter_name_for_arn,
                include_history=include_history,
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

    version: str = dataclasses.field()

    _applied_data: dict = dataclasses.field(init=False)
    _applied_secret_data: dict = dataclasses.field(init=False)
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
        self._applied_data = copy.deepcopy(self.data)
        self._applied_secret_data = copy.deepcopy(self.secret_data)
        apply_shared_value(self._applied_data)
        apply_shared_value(self._applied_secret_data)
        self._merged = merge_key_value(self._applied_data, self._applied_secret_data)

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
        env_name = self.EnvEnum.ensure_str(env_name)
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

        Example::

            class Config(BaseConfig):
                ...

                @classmethod
                def get_current_env(cls) -> str:
                    if "CI" in os.environ:
                        return EnvEnum.test.value
                    elif "AWS_LAMBDA_FUNCTION_NAME" in os.environ:
                        return EnvEnum.prod.value
                    else:
                        return EnvEnum.dev.value
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
        s3folder_config: T.Optional[str] = None,
    ):
        """
        Create and initialize the config object from configuration store.
        Currently, it supports:

        1. read from local config files.
        2. read from AWS Parameter Store. You have to specify
        3. read from AWS S3.

        :param env_class: the per environment config dataclass object.
        :param env_enum_class: the environment enumeration class.
        :param path_config: local file path to the non-sensitive config file.
        :param path_secret_config: local file path to the sensitive config file.
        :param parameter_name: the AWS Parameter name.
        :param parameter_with_encryption: is AWS Parameter turned on encryption?
        :param s3folder_config: the s3 folder uri where you store the config file.

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
                version="local",
            )
        elif (parameter_name is not None) and (
            parameter_with_encryption is not None
        ):  # pragma: no cover
            parameter = pysecret.Parameter.load(
                ssm_client=bsm.ssm_client,
                name=parameter_name,
                with_decryption=parameter_with_encryption,
            )
            if parameter is None:
                raise exc.ParameterNotExists(
                    f"SSM Parameter {parameter_name!r} not exist!"
                )
            parameter_data = parameter.json_dict
            return cls(
                data=parameter_data["data"],
                secret_data=parameter_data["secret_data"],
                Env=env_class,
                EnvEnum=env_enum_class,
                version=str(parameter.Version),
            )
        elif (parameter_name is not None) and (
            s3folder_config is not None
        ):  # pragma: no cover
            config_data, config_version = read_config(
                bsm=bsm,
                s3folder_config=s3folder_config,
                parameter_name=parameter_name,
            )
            return cls(
                data=config_data["data"],
                secret_data=config_data["secret_data"],
                Env=env_class,
                EnvEnum=env_enum_class,
                version=config_version,
            )
        else:
            raise ValueError(
                "The arguments has to meet one of these criteria:\n"
                "1. set both ``path_config`` and ``path_secret_config`` to indicate that "
                "you want to read config from local config json file.\n"
                "2. set both ``parameter_name`` and ``parameter_with_encryption`` "
                "to indicate that you want to read from AWS Parameter Store.\n"
                "3. set both ``parameter_name`` similar to 'my-project-dev' "
                "and ``s3folder_config`` similar to s3://my-bucket/my-project/ "
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
                env_name=ALL,
            )
        )

        # add per env parameter
        for env_name in self.EnvEnum:
            env_name = self.EnvEnum.ensure_str(env_name)
            env = self.get_env(env_name)
            parameter_name = env.parameter_name

            parameter_data = {
                "data": {
                    "_shared": {
                        k: v
                        for k, v in self.data.get("_shared", {}).items()
                        if k.startswith("*") or k.startswith(f"{env.env_name}.")
                    },
                    env.env_name: self.data[env.env_name],
                },
                "secret_data": {
                    "_shared": {
                        k: v
                        for k, v in self.secret_data.get("_shared", {}).items()
                        if k.startswith("*") or k.startswith(f"{env.env_name}.")
                    },
                    env.env_name: self.secret_data[env.env_name],
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

    def _get_specific_bsm(
        self,
        bsm: T.Union[
            "boto_session_manager.BotoSesManager",
            T.Dict[str, "boto_session_manager.BotoSesManager"],
        ],
        deployment: ConfigDeployment,
    ) -> "boto_session_manager.BotoSesManager":
        """
        Get the specific boto session manager for the deployment.

        :param bsm: the boto session manager.
        :param deployment: the deployment object.
        :return: the specific boto session manager.
        """
        if isinstance(bsm, dict):
            return bsm[deployment.env_name]
        else:
            return bsm

    def _get_specific_s3folder_config(
        self,
        s3folder_config: T.Union[str, T.Dict[str, str]],
        deployment: ConfigDeployment,
    ) -> str:
        """
        Get the specific boto session manager for the deployment.

        :param s3folder_config: s3 folder to store versioned config data.
        :param deployment: the deployment object.
        :return: the specific s3 folder to store versioned config data.
        """
        if isinstance(s3folder_config, dict):
            return s3folder_config[deployment.env_name]
        else:
            return s3folder_config

    # fmt: off
    def deploy(
        self,
        bsm: T.Union[
            "boto_session_manager.BotoSesManager",
            T.Dict[str, "boto_session_manager.BotoSesManager"],
        ],
        parameter_with_encryption: T.Optional[bool] = None,
        s3folder_config: T.Optional[
            T.Union[
                str,
                T.Dict[str, str],
            ]
        ] = None,
        tags: T.Optional[T.Dict[str, str]] = None,
        verbose: bool = True,
    ) -> T.List[ConfigDeployment]:
    # fmt: on
        """
        Deploy the project config of all environments to configuration store.
        Currently, it supports:

        1. deploy to AWS Parameter Store.
        2. deploy to AWS S3.

        Note:

            this function should ONLY run from the project admin's trusted laptop.

        Detailed Description of the Deployment Behavior

        Assume you have a project named "my-project" with two environments:
        dev and prod.

        **Deploy to AWS Parameter store**

        - Create three parameters named "my_project", "my_project-dev", and "my_project-prod".
            The "my_project" parameter contains information for all environments,
             while "my_project-dev" contains only development environment information,
             and "my_project-prod" contains only production environment information.
        - If the content of a parameter remains unchanged comparing to the latest version,
            a new version will not be created.

        **Deploy to AWS S3**

        If the value of  ``s3folder_config`` is "s3://my-bucket/my-project/",
        then it will create the following s3 objects:

        - "s3://my-bucket/my-project/my_project/my_project-latest.json"
        - "s3://my-bucket/my-project/my_project/my_project-000001.json"
        - "s3://my-bucket/my-project/my_project-dev/my_project-dev-latest.json"
        - "s3://my-bucket/my-project/my_project-dev/my_project-dev-000001.json"
        - "s3://my-bucket/my-project/my_project-prod/my_project-prod-latest.json"
        - "s3://my-bucket/my-project/my_project-prod/my_project-prod-000001.json"

        The naming convention is: "${s3folder_config}/${parameter_name}/${parameter_name}-${version}.json"

        :param bsm: one boto session manager or a dict of mapping from
            environment name to it's boto session manager (it has to have the "all")
        :param parameter_with_encryption: if set this value to either True or False,
            it will deploy the config to AWS parameter store.
        :param s3folder_config: one s3 folder uri or a dict of mapping from
            environment name to it's s3 folder uri (it has to have the "all").
            if this value is specified, it will deploy the config to AWS S3.
        :param tags: optional AWS resource tags to add to the parameter store
            or S3 object.
        :param verbose: whether to print out the log.

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
                specific_bsm = self._get_specific_bsm(bsm=bsm, deployment=deployment)
                deployment.deploy_to_ssm_parameter(
                    bsm=specific_bsm,
                    parameter_with_encryption=parameter_with_encryption,
                    tags=tags,
                    verbose=verbose,
                )
            return deployment_list
        elif s3folder_config is not None:
            deployment_list = self.prepare_deploy()
            for deployment in deployment_list:
                specific_bsm = self._get_specific_bsm(
                    bsm=bsm,
                    deployment=deployment,
                )
                specific_s3folder_config = self._get_specific_s3folder_config(
                    s3folder_config=s3folder_config,
                    deployment=deployment,
                )
                deployment.deploy_to_s3(
                    bsm=specific_bsm,
                    s3folder_config=specific_s3folder_config,
                    tags=tags,
                    verbose=verbose,
                )
            return deployment_list
        else:
            raise ValueError(
                "The arguments has to meet one of these criteria:\n"
                "1. set ``parameter_with_encryption`` to True or False to indicate that "
                "you want to deploy to AWS Parameter Store.\n"
                "2. set ``s3folder_config`` similar to s3://my-bucket/my-project/ "
                "to indicate that you want to deploy to S3."
            )

    # fmt: off
    def delete(
        self,
        bsm: T.Union[
            "boto_session_manager.BotoSesManager",
            T.Dict[str, "boto_session_manager.BotoSesManager"],
        ],
        use_parameter_store: T.Optional[bool] = None,
        s3folder_config: T.Optional[
            T.Union[
                str,
                T.Dict[str, str],
            ]
        ] = None,
        include_history: bool = False,
        verbose: bool = True,
    ):
    # fmt: on
        """
        Delete the all project config of all environments from configuration store.

        Currently, it supports:

        1. delete from AWS Parameter Store
        2. delete from AWS S3

        Note:

            this function should ONLY run from the project admin's trusted laptop.

        :param bsm: one boto session manager or a dict of mapping from
            environment name to it's boto session manager (it has to have the "all")
        :param use_parameter_store: if set this value to True, it will delete the config
            from AWS parameter store.
        :param s3folder_config: one s3 folder uri or a dict of mapping from
            environment name to it's s3 folder uri (it has to have the "all").
            if this value is specified, it will delete the config from AWS S3.
        :param include_history: if False, only delete the latest version,
            if True, delete all historical versions.
        :param verbose: whether to print out the log.
        """
        if (bsm is not None) and (use_parameter_store is True):
            deployment_list = self.prepare_deploy()
            for deployment in deployment_list:
                specific_bsm = self._get_specific_bsm(bsm=bsm, deployment=deployment)
                deployment.delete_from_ssm_parameter(
                    bsm=specific_bsm,
                    verbose=verbose,
                )
            return deployment_list
        elif (bsm is not None) and (s3folder_config is not None):
            deployment_list = self.prepare_deploy()
            for deployment in deployment_list:
                specific_bsm = self._get_specific_bsm(
                    bsm=bsm,
                    deployment=deployment,
                )
                specific_s3folder_config = self._get_specific_s3folder_config(
                    s3folder_config=s3folder_config,
                    deployment=deployment,
                )
                deployment.delete_from_s3(
                    bsm=specific_bsm,
                    s3folder_config=specific_s3folder_config,
                    include_history=include_history,
                    verbose=verbose,
                )
            return deployment_list
        else:
            raise ValueError(
                "The arguments has to meet one of these criteria:\n"
                "1. set ``use_parameter_store`` to True to indicate that "
                "you want to delete config from AWS Parameter Store.\n"
                "2. set ``s3folder_config`` similar to s3://my-bucket/my-project/ "
                "to indicate that you want to delete config file from S3."
            )

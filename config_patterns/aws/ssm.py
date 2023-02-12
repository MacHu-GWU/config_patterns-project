# -*- coding: utf-8 -*-

"""
AWS System Manager utility functions
"""

import typing as T

try:
    import boto3
    import boto_session_manager
    import pysecret
    import aws_console_url
except ImportError:  # pragma: no cover
    pass


def deploy_parameter(
    bsm: "boto_session_manager.BotoSesManager",
    parameter_name: str,
    parameter_data: dict,
    parameter_with_encryption: bool,
    tags: T.Optional[dict] = None,
):
    """
    Deploy (Create or Update) AWS SSM parameter store.

    :param bsm:
    :param parameter_name:
    :param parameter_data:
    :param parameter_with_encryption:
    :param tags:
    """
    aws_console = aws_console_url.AWSConsole(aws_region=bsm.aws_region)
    print(f"🚀️ deploy SSM Parameter {parameter_name!r} ...")
    print(f"preview at: {aws_console.ssm.get_parameter(parameter_name)}")
    parameter = pysecret.deploy_parameter(
        bsm.ssm_client,
        name=parameter_name,
        data=parameter_data,
        use_default_kms_key=parameter_with_encryption,
        type_is_secure_string=True,
        tier_is_intelligent=True,
        tags=tags,
        overwrite=True,
    )
    if parameter is None:
        print("parameter data is the same as existing one, do nothing.")
    else:
        print(f"successfully deployed version {parameter.Version}")
    print("done!")


def delete_parameter(
    bsm: "boto_session_manager.BotoSesManager",
    parameter_name: str,
):
    """
    Delete AWS SSM parameter.

    Ref:

    - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm.html#SSM.Client.delete_parameter
    """
    aws_console = aws_console_url.AWSConsole(aws_region=bsm.aws_region)
    print(f"🗑️ delete SSM Parameter {parameter_name!r} ...")
    print(f"verify at: {aws_console.ssm.get_parameter(parameter_name)}")

    try:
        bsm.ssm_client.delete_parameter(Name=parameter_name)
    except Exception as e:
        if "ParameterNotFound" in str(e):
            print("not exists, do nothing.")
        else:
            raise e

    print("done!")
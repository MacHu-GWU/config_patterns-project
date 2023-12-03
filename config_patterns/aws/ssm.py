# -*- coding: utf-8 -*-

"""
AWS System Manager utility functions
"""

import typing as T

try:
    import boto3
    import boto_session_manager
    import pysecret
    import aws_console_url.api as aws_console_url
except ImportError:  # pragma: no cover
    pass

from ..logger import logger


@logger.start_and_end(
    msg="deploy config to SSM parameter",
)
def deploy_parameter(
    bsm: "boto_session_manager.BotoSesManager",
    parameter_name: str,
    parameter_data: dict,
    parameter_with_encryption: bool,
    tags: T.Optional[dict] = None,
) -> T.Optional["pysecret.Parameter"]:
    """
    Deploy (Create or Update) AWS SSM parameter store.

    :param bsm: the ``boto_session_manager.BotoSesManager`` object.
    :param parameter_name: parameter name.
    :param parameter_data: parameter data in python dict.
    :param parameter_with_encryption: do you want to encrypt the data at rest?
    :param tags: optional key value tags.

    :return: a ``pysecret.Parameter`` object to indicate the deployed parameter.
        if returns None, then no deployment happened.
    """
    aws_console = aws_console_url.AWSConsole(
        aws_account_id=bsm.aws_account_id,
        aws_region=bsm.aws_region,
        bsm=bsm,
    )
    logger.info(f"🚀️ deploy SSM Parameter {parameter_name!r} ...")
    logger.info(f"preview at: {aws_console.ssm.get_parameter(parameter_name)}")
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
        logger.info("parameter data is the same as existing one, do nothing.")
    else:
        logger.info(f"successfully deployed version {parameter.Version}")
    return parameter


@logger.start_and_end(
    msg="delete config from SSM parameter",
)
def delete_parameter(
    bsm: "boto_session_manager.BotoSesManager",
    parameter_name: str,
) -> bool:
    """
    Delete AWS SSM parameter.

    Ref:

    - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm.html#SSM.Client.delete_parameter

    :return: a boolean value indicating whether a deletion happened.
    """
    aws_console = aws_console_url.AWSConsole(
        aws_account_id=bsm.aws_account_id,
        aws_region=bsm.aws_region,
        bsm=bsm,
    )
    logger.info(f"🗑️ delete SSM Parameter {parameter_name!r} ...")
    logger.info(f"verify at: {aws_console.ssm.get_parameter(parameter_name)}")

    try:
        bsm.ssm_client.delete_parameter(Name=parameter_name)
        delete_happened = True
    except Exception as e:
        if "ParameterNotFound" in str(e):
            logger.info("not exists, do nothing.")
            delete_happened = False
        else:  # pragma: no cover
            raise e

    logger.info("done!")
    return delete_happened

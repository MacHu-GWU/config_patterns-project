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

    aws_secret = pysecret.AWSSecret(boto_session=bsm.boto_ses)
    exists: bool
    try:
        existing_parameter_data = aws_secret.get_parameter_data(
            name=parameter_name,
            with_encryption=parameter_with_encryption,
        )
        exists = True
    except Exception as e:
        if "ParameterNotFound" in str(e):
            exists = False
        else:
            raise e

    kwargs = dict(
        name=parameter_name,
        parameter_data=parameter_data,
        use_default_kms_key=parameter_with_encryption,
    )

    if exists is False:
        print("not exists, create a new one")
        if tags:
            kwargs["tags"] = tags
        kwargs["update_mode"] = aws_secret.UpdateModeEnum.create
        aws_secret.deploy_parameter(**kwargs)
    else:
        if parameter_data != existing_parameter_data:
            print("already exists, update the parameter data.")
            kwargs["update_mode"] = aws_secret.UpdateModeEnum.upsert
            aws_secret.deploy_parameter(**kwargs)
        else:
            print("parameter data is the same as existing one, do nothing.")
    print("done!")

# -*- coding: utf-8 -*-

"""
AWS S3 utility functions
"""

import typing as T
import json

try:
    import boto3
    import boto_session_manager
    import aws_console_url
except ImportError:  # pragma: no cover
    pass


def deploy_config(
    bsm: "boto_session_manager.BotoSesManager",
    s3path_config: str,
    config_data: dict,
    tags: T.Optional[dict] = None,
) -> str:
    """
    Deploy config to AWS S3

    :param bsm: the ``boto_session_manager.BotoSesManager`` object.
    :param s3path_config: s3 object uri for config json file.
    :param config_data: config data.
    :param tags: optional key value tags.
    """
    parts = s3path_config.split("/", 3)
    bucket = parts[2]
    key = parts[3]

    aws_console = aws_console_url.AWSConsole(aws_region=bsm.aws_region)
    print(f"🚀️ deploy config file {s3path_config} ...")
    print(f"preview at: {aws_console.s3.get_console_url(bucket, key)}")

    kwargs = dict(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(config_data),
    )
    if tags:
        tagging = "&".join([
            f"{key}={value}"
            for key, value in tags.items()
        ])
        kwargs["Tagging"] = tagging
    bsm.s3_client.put_object(**kwargs)
    print("done!")
    return f"s3://{bucket}/{key}"


def delete_config(
    bsm: "boto_session_manager.BotoSesManager",
    s3path_config: str,
) -> bool:
    """
    Delete config from AWS S3

    Ref:

    - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.delete_object

    :return: a boolean value indicating whether a deletion happened.

    TODO: do a test when the config file doesn't exist.
    """
    parts = s3path_config.split("/", 3)
    bucket = parts[2]
    key = parts[3]

    aws_console = aws_console_url.AWSConsole(aws_region=bsm.aws_region)
    print(f"🗑️ delete config file {s3path_config} ...")
    print(f"preview at: {aws_console.s3.get_console_url(bucket, key)}")

    bsm.s3_client.delete_object(
        Bucket=bucket,
        Key=key,
    )

    print("done!")
    return True

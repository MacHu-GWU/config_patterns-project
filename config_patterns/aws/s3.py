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
):
    """
    Deploy config to AWS S3

    :param bsm:
    :param s3dir_config:
    :param config_data:
    :param tags:
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

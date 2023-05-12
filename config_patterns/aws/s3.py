# -*- coding: utf-8 -*-

"""
AWS S3 utility functions
"""

import typing as T
import json
import dataclasses

try:
    import boto3
    import boto_session_manager
    import aws_console_url
except ImportError:  # pragma: no cover
    pass

from ..logger import logger


@dataclasses.dataclass
class S3Object:
    expiration: T.Optional[str] = dataclasses.field(default=None)
    etag: T.Optional[str] = dataclasses.field(default=None)
    checksum_crc32: T.Optional[str] = dataclasses.field(default=None)
    checksum_crc32c: T.Optional[str] = dataclasses.field(default=None)
    checksum_sha1: T.Optional[str] = dataclasses.field(default=None)
    checksum_sha256: T.Optional[str] = dataclasses.field(default=None)
    server_side_encryption: T.Optional[str] = dataclasses.field(default=None)
    version_id: T.Optional[str] = dataclasses.field(default=None)
    sse_customer_algorithm: T.Optional[str] = dataclasses.field(default=None)
    sse_customer_key_md5: T.Optional[str] = dataclasses.field(default=None)
    see_kms_key_id: T.Optional[str] = dataclasses.field(default=None)
    sse_kms_encryption_context: T.Optional[str] = dataclasses.field(default=None)
    bucket_key_enabled: T.Optional[bool] = dataclasses.field(default=None)
    request_charged: T.Optional[str] = dataclasses.field(default=None)

    @classmethod
    def from_put_object_response(cls, response: dict) -> "S3Object":
        return cls(
            expiration=response.get("Expiration"),
            etag=response.get("ETag"),
            checksum_crc32=response.get("ChecksumCRC32"),
            checksum_crc32c=response.get("ChecksumCRC32C"),
            checksum_sha1=response.get("ChecksumSHA1"),
            checksum_sha256=response.get("ChecksumSHA256"),
            server_side_encryption=response.get("ServerSideEncryption"),
            version_id=response.get("VersionId"),
            sse_customer_algorithm=response.get("SSECustomerAlgorithm"),
            sse_customer_key_md5=response.get("SSECustomerKeyMD5"),
            see_kms_key_id=response.get("SSEKMSKeyId"),
            sse_kms_encryption_context=response.get("SSEKMSEncryptionContext"),
            bucket_key_enabled=response.get("BucketKeyEnabled"),
            request_charged=response.get("RequestCharged"),
        )


@logger.start_and_end(
    msg="deploy config file to S3",
)
def deploy_config(
    bsm: "boto_session_manager.BotoSesManager",
    s3path_config: str,
    config_data: dict,
    tags: T.Optional[dict] = None,
) -> T.Optional[S3Object]:
    """
    Deploy config to AWS S3

    :param bsm: the ``boto_session_manager.BotoSesManager`` object.
    :param s3path_config: s3 object uri for config json file.
    :param config_data: config data.
    :param tags: optional key value tags.

    :return: a :class:`S3Object` to indicate the deployed config file on S3.
        if returns None, then no deployment happened.
    """
    parts = s3path_config.split("/", 3)
    bucket = parts[2]
    key = parts[3]

    aws_console = aws_console_url.AWSConsole(aws_region=bsm.aws_region)
    logger.info(f"🚀️ deploy config file {s3path_config} ...")
    logger.info(f"preview at: {aws_console.s3.get_console_url(bucket, key)}")

    try:
        response = bsm.s3_client.get_object(Bucket=bucket, Key=key)
        existing_config_data = json.loads(response["Body"].read().decode("utf-8"))
        if existing_config_data == config_data:
            logger.info("config data is the same as existing one, do nothing.")
            return None
    except Exception as e:  # pragma: no cover
        if "The specified key does not exist" in str(e):
            pass
        else:
            raise e

    kwargs = dict(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(config_data, indent=4),
        ContentType="application/json",
    )
    if tags:
        tagging = "&".join([f"{key}={value}" for key, value in tags.items()])
        kwargs["Tagging"] = tagging
    response = bsm.s3_client.put_object(**kwargs)
    logger.info("done!")
    return S3Object.from_put_object_response(response)


@logger.start_and_end(
    msg="delete config file from S3",
)
def delete_config(
    bsm: "boto_session_manager.BotoSesManager",
    s3path_config: str,
) -> bool:
    """
    Delete config from AWS S3

    Ref:

    - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.delete_object

    :return: a boolean value indicating whether a deletion happened.
    """
    parts = s3path_config.split("/", 3)
    bucket = parts[2]
    key = parts[3]

    aws_console = aws_console_url.AWSConsole(aws_region=bsm.aws_region)
    logger.info(f"🗑️ delete config file {s3path_config} ...")
    logger.info(f"preview at: {aws_console.s3.get_console_url(bucket, key)}")

    try:
        bsm.s3_client.head_object(Bucket=bucket, Key=key)
    except Exception as e:  # pragma: no cover
        if "Not Found" in str(e):
            logger.info("not exists, do nothing.")
            return False
        else:
            raise e

    bsm.s3_client.delete_object(
        Bucket=bucket,
        Key=key,
    )

    logger.info("done!")
    return True

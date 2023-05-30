# -*- coding: utf-8 -*-

"""
AWS S3 utility functions.

Variable naming convention:

- s3path_xyz: S3Path object for a file. Example: ``S3Path("s3://bucket/file.txt")``
- s3dir_xyz: S3Path object for a folder. Example: ``S3Path("s3://bucket/folder/")``
- s3bkt_xyz: S3Path object for a bucket. Example: ``S3Path("s3://bucket/")``
- s3file_xyz: S3 URI string for a file. Example: ``"s3://bucket/file.txt"``
- s3folder_xyz: S3 URI string for a file. Example: ``"s3://bucket/folder/"``
"""

import typing as T
import json
import dataclasses

try:
    import boto3
    import boto_session_manager
    import aws_console_url
    from s3pathlib import S3Path
except ImportError:  # pragma: no cover
    pass

from ..logger import logger
from ..vendor.better_enum import BetterStrEnum


ZFILL = 6
KEY_CONFIG_VERSION = "config_version"


class S3BucketVersionStatus(BetterStrEnum):
    NotEnabled = "NotEnabled"
    Enabled = "Enabled"
    Suspended = "Suspended"

    def is_not_enabled(self) -> bool:
        return self.value == S3BucketVersionStatus.NotEnabled.value

    def is_enabled(self) -> bool:
        return self.value == S3BucketVersionStatus.Enabled.value

    def is_suspended(self) -> bool:
        return self.value == S3BucketVersionStatus.Suspended.value


def get_bucket_version_status(
    bsm: "boto_session_manager.BotoSesManager",
    bucket: str,
) -> S3BucketVersionStatus:
    """
    Check if the S3 bucket turns on versioning.
    """
    res = bsm.s3_client.get_bucket_versioning(Bucket=bucket)
    status = res.get("Status", S3BucketVersionStatus.NotEnabled.value)
    S3BucketVersionStatus.ensure_is_valid_value(status)
    return S3BucketVersionStatus.get_by_value(status)


def _ensure_bucket_versioning_is_not_suspended(
    bucket: str,
    status: S3BucketVersionStatus,
):
    if status.is_suspended():
        raise ValueError(
            f"bucket {bucket!r} versioning is suspended. "
            f"I don't know how to handle this situation."
        )


@dataclasses.dataclass
class S3Object:
    bucket: T.Optional[str] = dataclasses.field(default=None)
    key: T.Optional[str] = dataclasses.field(default=None)
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


def _show_deploy_info(s3path: S3Path):
    logger.info(f"🚀️ deploy config file/files at {s3path.uri} ...")
    logger.info(f"preview at: {s3path.console_url}")


@logger.start_and_end(
    msg="deploy config file to S3",
)
def deploy_config(
    bsm: "boto_session_manager.BotoSesManager",
    s3folder_config: str,
    parameter_name: str,
    config_data: dict,
    tags: T.Optional[dict] = None,
) -> T.Optional[S3Object]:
    """
    Deploy config to AWS S3

    :param bsm: the ``boto_session_manager.BotoSesManager`` object.
    :param s3folder_config: s3 directory uri for this config json file.
    :param parameter_name: the parameter name for this config.
    :param config_data: config data.
    :param version_enabled: whether to enable versioning for this config file.
    :param tags: optional key value tags.

    :return: a :class:`S3Object` to indicate the deployed config file on S3.
        if returns None, then no deployment happened.
    """
    s3dir_config = S3Path(s3folder_config).to_dir()
    s3_bucket_version_status = get_bucket_version_status(
        bsm=bsm, bucket=s3dir_config.bucket
    )
    _ensure_bucket_versioning_is_not_suspended(
        bucket=s3dir_config.bucket,
        status=s3_bucket_version_status,
    )
    if s3_bucket_version_status.is_not_enabled():
        s3path_latest = s3dir_config.joinpath(
            parameter_name, f"{parameter_name}-latest.json"
        )
    elif s3_bucket_version_status.is_enabled():
        s3path_latest = s3dir_config.joinpath(f"{parameter_name}.json")
    else:  # pragma: no cover
        raise NotImplementedError

    logger.info(f"🚀️ deploy config file {s3path_latest.uri} ...")
    logger.info(f"preview at: {s3path_latest.console_url}")

    already_exists = s3path_latest.exists()
    if already_exists:
        existing_config_data = json.loads(s3path_latest.read_text())
        if existing_config_data == config_data:
            logger.info("config data is the same as existing one, do nothing.")
            return None

    if s3_bucket_version_status.is_not_enabled():
        if already_exists:
            latest_version = int(s3path_latest.metadata[KEY_CONFIG_VERSION])
            new_version = latest_version + 1
            s3path_latest.write_text(
                json.dumps(config_data, indent=4),
                content_type="application/json",
                metadata={KEY_CONFIG_VERSION: str(new_version)},
                tags=tags,
            )
            basename = f"{parameter_name}-{str(new_version).zfill(ZFILL)}.json"
            s3path_versioned = s3path_latest.change(new_basename=basename)
            s3path_res = s3path_versioned.write_text(
                json.dumps(config_data, indent=4),
                content_type="application/json",
                metadata={KEY_CONFIG_VERSION: str(new_version)},
                tags=tags,
            )
            s3object = S3Object.from_put_object_response(s3path_res._meta)
        else:
            versions: T.List[int] = list()
            for s3path in s3path_latest.parent.iter_objects():
                try:
                    versions.append(int(s3path.fname.split("-")[-1]))
                except:
                    pass
            if len(versions):
                latest_version = max(versions)
            else:
                latest_version = 0
            new_version = latest_version + 1

            s3path_latest.write_text(
                json.dumps(config_data, indent=4),
                content_type="application/json",
                metadata={KEY_CONFIG_VERSION: str(new_version)},
                tags=tags,
            )
            basename = f"{parameter_name}-{str(new_version).zfill(ZFILL)}.json"
            s3path_versioned = s3path_latest.change(new_basename=basename)
            s3path_res = s3path_versioned.write_text(
                json.dumps(config_data, indent=4),
                content_type="application/json",
                metadata={KEY_CONFIG_VERSION: str(new_version)},
                tags=tags,
            )
            s3object = S3Object.from_put_object_response(s3path_res._meta)

    else:
        if already_exists:
            # latest_version = int(s3path_latest.metadata[KEY_CONFIG_VERSION])
            # new_version = latest_version + 1
            s3path_res = s3path_latest.write_text(
                json.dumps(config_data, indent=4),
                content_type="application/json",
                tags=tags,
            )
            print(s3path_res._meta)
            s3object = S3Object.from_put_object_response(s3path_res._meta)
            # basename = f"{parameter_name}-{str(new_version).zfill(ZFILL)}.json"
            # s3path_versioned = s3path_latest.change(new_basename=basename)
            # s3path_res = s3path_versioned.write_text(
            #     json.dumps(config_data, indent=4),
            #     content_type="application/json",
            #     metadata={KEY_CONFIG_VERSION: str(new_version)},
            #     tags=tags,
            # )
            # s3object = S3Object.from_put_object_response(s3path_res._meta)
            pass
        else:
            # versions: T.List[int] = list()
            # for s3path in s3path_latest.parent.iter_objects():
            #     try:
            #         versions.append(int(s3path.fname.split("-")[-1]))
            #     except:
            #         pass
            # if len(versions):
            #     latest_version = max(versions)
            # else:
            #     latest_version = 0
            # latest_version = 0
            # new_version = latest_version + 1

            s3path_res = s3path_latest.write_text(
                json.dumps(config_data, indent=4),
                content_type="application/json",
                tags=tags,
            )
            s3object = S3Object.from_put_object_response(s3path_res._meta)

    #
    # kwargs = dict(
    #     Bucket=bucket,
    #     Key=key,
    #     Body=json.dumps(config_data, indent=4),
    #     ContentType="application/json",
    # )
    # if tags:
    #     tagging = "&".join([f"{key}={value}" for key, value in tags.items()])
    #     kwargs["Tagging"] = tagging
    # response = bsm.s3_client.put_object(**kwargs)
    # logger.info("done!")
    # s3object = S3Object.from_put_object_response(response)
    # s3object.bucket = bucket
    # s3object.key = key
    logger.info("done!")
    return s3object


def _show_delete_info(s3path: S3Path):
    logger.info(f"🗑️ delete config file/files at: {s3path.uri} ...")
    logger.info(f"preview at: {s3path.console_url}")


@logger.start_and_end(
    msg="delete config file from S3",
)
def delete_config(
    bsm: "boto_session_manager.BotoSesManager",
    s3folder_config: str,
    parameter_name: str,
    include_history: bool = False,
) -> bool:
    """
    Delete config from AWS S3. The config file to be removed is:

    For versioning disabled bucket:

    - ``${include_history} = False``: ``${s3folder_config}/${parameter_name}/${parameter_name}-latest.json``
    - ``${include_history} = True``: ``${s3folder_config}/${parameter_name}/${parameter_name}-latest.json``
        and ``${s3folder_config}/${parameter_name}/${parameter_name}-1.json``,
        ``${s3folder_config}/${parameter_name}/${parameter_name}-2.json``,
        ``${s3folder_config}/${parameter_name}/${parameter_name}-3.json``, ...

    For versioning enabled bucket:

    - ``${include_history} = False``: ``${s3folder_config}/${parameter_name}.json``
        only put delete marker on the latest version.
    - ``${include_history} = True``: ``${s3folder_config}/${parameter_name}/${parameter_name}.json``
        delete all historical versions permanently.

    :param s3folder_config: s3 directory uri for this config json file.
    :param parameter_name: the parameter name for this config.
    :param include_history: whether to delete all historical versions permanently.

    Ref:

    - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.delete_object

    :return: a boolean value indicating whether a deletion happened.
    """
    s3dir_config = S3Path(s3folder_config).to_dir()
    s3_bucket_version_status = get_bucket_version_status(
        bsm=bsm, bucket=s3dir_config.bucket
    )
    _ensure_bucket_versioning_is_not_suspended(
        bucket=s3dir_config.bucket, status=s3_bucket_version_status
    )
    if s3_bucket_version_status.is_not_enabled():
        s3path_latest = s3dir_config.joinpath(
            parameter_name,
            f"{parameter_name}-latest.json",
        )
        if include_history:
            _show_delete_info(s3path_latest.parent)
            s3path_latest.parent.delete()
        else:
            _show_delete_info(s3path_latest)
            s3path_latest.delete()
    elif s3_bucket_version_status.is_enabled():
        s3path_latest = s3dir_config.joinpath(f"{parameter_name}.json")
        _show_delete_info(s3path_latest)
        s3path_latest.delete(is_hard_delete=include_history)
    else:  # pragma: no cover
        raise NotImplementedError

    logger.info("done!")
    return True

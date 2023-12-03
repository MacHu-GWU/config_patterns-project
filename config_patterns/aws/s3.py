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

from botocore.exceptions import ClientError
from boto_session_manager import BotoSesManager
from func_args import NOTHING
from s3pathlib import S3Path

from .. import exc
from ..logger import logger
from ..jsonutils import json_loads
from ..utils import sha256_of_config_data
from ..vendor.better_enum import BetterStrEnum


ZFILL = 6
KEY_CONFIG_VERSION = "config_version"
KEY_CONFIG_SHA256 = "config_sha256"


# ------------------------------------------------------------------------------
# S3 bucket version status
# ------------------------------------------------------------------------------
class S3BucketVersionStatus(BetterStrEnum):
    """
    Enumerate the status of S3 bucket versioning.

    - NotEnabled: bucket doesn't turn on versioning.
    - Enabled: bucket turns on versioning.
    - Suspended: bucket turns on versioning but is suspended. We don't store
        config files in a bucket with 'suspended' status.
    """

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
    bsm: BotoSesManager,
    bucket: str,
) -> S3BucketVersionStatus:
    """
    Get the version status of a S3 bucket.

    :param bsm: the ``boto_session_manager.BotoSesManager`` object.
    :param bucket: the bucket name.
    """
    res = bsm.s3_client.get_bucket_versioning(Bucket=bucket)
    status = res.get("Status", S3BucketVersionStatus.NotEnabled.value)
    S3BucketVersionStatus.ensure_is_valid_value(status)
    return S3BucketVersionStatus.get_by_value(status)


def _ensure_bucket_versioning_is_not_suspended(
    bucket: str,
    status: S3BucketVersionStatus,
):  # pragma: no cover
    """
    We don't store config files in a bucket with 'suspended' status. We could
    use this function to ensure the bucket versioning is not suspended.
    """
    if status.is_suspended():
        raise exc.S3BucketVersionSuspendedError(
            f"bucket {bucket!r} versioning is suspended. "
            f"I don't know how to handle this situation."
        )


@dataclasses.dataclass
class S3Object:
    """
    This class represents an S3 object.
    """

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
        """
        Create an ``S3Object`` object from the response of s3_client.put_object(...).
        """
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


@dataclasses.dataclass
class S3Parameter:
    """
    This class represents a S3 parameter. It is actually a file in a S3 bucket.
    The S3 bucket could have version enabled or not enabled.

    :param s3dir_config: the S3 directory where the parameter is stored.
        it should not include any file name information.
    :param parameter_name: the parameter name that will be used as the file name.
    :param version_status: the :class:`S3BucketVersionStatus` enum object.
    :param version_enabled: whether the S3 bucket versioning is enabled.
    :param s3path_latest: the S3 path of the file representing the latest version
        of the parameter.

    When deploying a new version of parameter, for versioning disabled bucket,
    it should deploy two S3 objects:

    - ``${s3folder_config}/${parameter_name}/${parameter_name}-latest.json``
    - ``${s3folder_config}/${parameter_name}/${parameter_name}-${1, 2, 3, ...}.json``,

    For versioning enabled bucket, it should deploy only one S3 object, it creates
    a new version of the object:

    - ``${s3folder_config}/${parameter_name}.json``

    .. seealso::

        - :meth:`~S3Parameter.deploy_latest_when_version_not_enabled`
        - :meth:`~S3Parameter.deploy_latest_when_version_is_enabled`
    """

    s3dir_config: S3Path = dataclasses.field()
    parameter_name: str = dataclasses.field()
    version_status: S3BucketVersionStatus = dataclasses.field()
    version_enabled: bool = dataclasses.field()
    s3path_latest: S3Path = dataclasses.field()

    @classmethod
    def new(
        cls,
        bsm: BotoSesManager,
        s3folder_config: str,
        parameter_name: str,
    ) -> "S3Parameter":
        s3dir_config = S3Path(s3folder_config).to_dir()
        s3_bucket_version_status = get_bucket_version_status(
            bsm=bsm,
            bucket=s3dir_config.bucket,
        )
        _ensure_bucket_versioning_is_not_suspended(
            bucket=s3dir_config.bucket,
            status=s3_bucket_version_status,
        )
        if s3_bucket_version_status.is_enabled():
            s3path_latest = s3dir_config.joinpath(f"{parameter_name}.json")
        else:
            s3path_latest = s3dir_config.joinpath(
                parameter_name,
                f"{parameter_name}-latest.json",
            )
        return cls(
            s3dir_config=s3dir_config,
            parameter_name=parameter_name,
            version_status=s3_bucket_version_status,
            version_enabled=s3_bucket_version_status.is_enabled(),
            s3path_latest=s3path_latest,
        )

    def read_latest(self, bsm: BotoSesManager) -> T.Tuple[dict, str]:
        """
        Read the latest config data and config version from S3.

        For versioning disabled bucket, the version is 1, 2, 3, ...
        For versioning enabled bucket, the version is the version id of the S3 object.
        """
        try:
            config_data = json_loads(self.s3path_latest.read_text(bsm=bsm))
        except ClientError as e:
            if "NoSuchKey" in str(e):
                raise exc.S3ObjectNotExist(
                    f"S3 object {self.s3path_latest.uri} not exist."
                )
            else:  # pragma: no cover
                raise e
        if self.version_enabled:
            config_version = self.s3path_latest.version_id
        else:
            config_version = self.s3path_latest.metadata[KEY_CONFIG_VERSION]
        return config_data, config_version

    def get_latest_config_version_when_version_not_enabled(
        self,
        bsm: BotoSesManager,
    ) -> T.Optional[int]:
        """
        Todo: add docstring
        """
        if self.s3path_latest.exists(bsm=bsm):
            return int(self.s3path_latest.metadata[KEY_CONFIG_VERSION])
        else:
            versions: T.List[int] = list()
            for s3path in self.s3path_latest.parent.iter_objects(bsm=bsm):
                try:
                    versions.append(int(s3path.fname.split("-")[-1]))
                except:  # pragma: no cover
                    pass
            if len(versions):
                return max(versions)
            else:
                return None

    def get_latest_config_version_when_version_is_enabled(
        self,
        bsm: BotoSesManager,
    ) -> T.Optional[str]:  # pragma: no cover
        """
        Todo: add docstring
        """
        s3path_list = self.s3path_latest.list_object_versions(limit=2, bsm=bsm).all()
        if len(s3path_list) == 0:
            return None
        else:
            if s3path_list[0].is_delete_marker():
                return s3path_list[1].version_id
            else:
                return s3path_list[0].version_id

    def deploy_latest_when_version_not_enabled(
        self,
        bsm: BotoSesManager,
        config_data: dict,
        config_version: str,
        tags: T.Optional[T.Dict[str, str]] = NOTHING,
    ) -> S3Object:
        """
        Todo: add docstring
        """
        basename = f"{self.parameter_name}-{config_version.zfill(ZFILL)}.json"
        s3path_versioned = self.s3path_latest.change(new_basename=basename)
        content = json.dumps(config_data, indent=4)
        config_sha256 = sha256_of_config_data(config_data)
        s3path_res = s3path_versioned.write_text(
            content,
            content_type="application/json",
            metadata={
                KEY_CONFIG_VERSION: config_version,
                KEY_CONFIG_SHA256: config_sha256,
            },
            tags=tags,
            bsm=bsm,
        )
        s3object = S3Object.from_put_object_response(s3path_res._meta)

        s3path_versioned.copy_to(self.s3path_latest, overwrite=True, bsm=bsm)
        return s3object

    def deploy_latest_when_version_is_enabled(
        self,
        bsm: BotoSesManager,
        config_data: dict,
        tags: T.Optional[T.Dict[str, str]] = NOTHING,
    ) -> S3Object:
        """
        Todo: add docstring
        """
        content = json.dumps(config_data, indent=4)
        config_sha256 = sha256_of_config_data(config_data)
        s3path_res = self.s3path_latest.write_text(
            content,
            content_type="application/json",
            metadata={
                KEY_CONFIG_SHA256: config_sha256,
            },
            tags=tags,
            bsm=bsm,
        )
        s3object = S3Object.from_put_object_response(s3path_res._meta)
        return s3object


def _show_deploy_info(s3path: S3Path):
    logger.info(f"🚀️ deploy config file/files at {s3path.uri} ...")
    logger.info(f"preview at: {s3path.console_url}")


def read_config(
    bsm: BotoSesManager,
    s3folder_config: str,
    parameter_name: str,
) -> T.Tuple[dict, str]:
    """
    Read config data and config version from S3.

    :return: config data and version
    """
    s3parameter = S3Parameter.new(
        bsm=bsm,
        s3folder_config=s3folder_config,
        parameter_name=parameter_name,
    )
    return s3parameter.read_latest(bsm=bsm)


@logger.start_and_end(
    msg="deploy config file to S3",
)
def deploy_config(
    bsm: BotoSesManager,
    s3folder_config: str,
    parameter_name: str,
    config_data: dict,
    tags: T.Optional[dict] = NOTHING,
) -> T.Optional[S3Object]:
    """
    Deploy config to AWS S3

    :param bsm: the ``boto_session_manager.BotoSesManager`` object.
    :param s3dir_config: the S3 directory where the parameter is stored.
        it should not include any file name information.
    :param parameter_name: the parameter name that will be used as the file name.
    :param config_data: config data.
    :param tags: optional key value tags.

    :return: a :class:`S3Object` to indicate the deployed config file on S3.
        if returns None, then no deployment happened.
    """
    s3parameter = S3Parameter.new(
        bsm=bsm,
        s3folder_config=s3folder_config,
        parameter_name=parameter_name,
    )
    s3path_latest = s3parameter.s3path_latest
    _show_deploy_info(s3path=s3path_latest)

    already_exists = s3path_latest.exists(bsm=bsm)
    if already_exists:
        existing_config_data, _ = s3parameter.read_latest(bsm=bsm)
        if existing_config_data == config_data:
            logger.info("config data is the same as existing one, do nothing.")
            return None

    if s3parameter.version_enabled is False:
        latest_version = s3parameter.get_latest_config_version_when_version_not_enabled(
            bsm=bsm,
        )
        if latest_version is None:
            new_version = 1
        else:
            new_version = latest_version + 1
        s3object = s3parameter.deploy_latest_when_version_not_enabled(
            bsm=bsm,
            config_data=config_data,
            config_version=str(new_version),
            tags=tags,
        )
    else:
        s3object = s3parameter.deploy_latest_when_version_is_enabled(
            bsm=bsm,
            config_data=config_data,
            tags=tags,
        )
    logger.info("done!")
    return s3object


def _show_delete_info(s3path: S3Path):
    logger.info(f"🗑️ delete config file/files at: {s3path.uri} ...")
    logger.info(f"preview at: {s3path.console_url}")


@logger.start_and_end(
    msg="delete config file from S3",
)
def delete_config(
    bsm: BotoSesManager,
    s3folder_config: str,
    parameter_name: str,
    include_history: bool = False,
) -> bool:
    """
    Delete config from AWS S3. The config file to be removed is:

    For versioning disabled bucket:

    - ``${include_history} = False``:
        - ``${s3folder_config}/${parameter_name}/${parameter_name}-latest.json``
    - ``${include_history} = True``:
        - ``${s3folder_config}/${parameter_name}/${parameter_name}-latest.json``
        - ``${s3folder_config}/${parameter_name}/${parameter_name}-1.json``
        - ``${s3folder_config}/${parameter_name}/${parameter_name}-2.json``
        - ``${s3folder_config}/${parameter_name}/${parameter_name}-3.json``
        - ...

    For versioning enabled bucket:

    - ``${include_history} = False``:
        - ``${s3folder_config}/${parameter_name}.json``, only put delete marker
            on the latest version.
    - ``${include_history} = True``:
        - ``${s3folder_config}/${parameter_name}/${parameter_name}.json`` delete
            all historical versions permanently.

    :param s3dir_config: the S3 directory where the parameter is stored.
        it should not include any file name information.
    :param parameter_name: the parameter name that will be used as the file name.
    :param include_history: whether to delete all historical versions permanently.

    Ref:

    - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.delete_object

    :return: a boolean value indicating whether a deletion happened.
    """
    s3parameter = S3Parameter.new(
        bsm=bsm,
        s3folder_config=s3folder_config,
        parameter_name=parameter_name,
    )
    s3path_latest = s3parameter.s3path_latest
    if s3parameter.version_enabled is False:
        if include_history:
            _show_delete_info(s3path_latest.parent)
            s3path_latest.parent.delete(bsm=bsm)
        else:
            _show_delete_info(s3path_latest)
            s3path_latest.delete(bsm=bsm)
    else:
        _show_delete_info(s3path_latest)
        s3path_latest.delete(bsm=bsm, is_hard_delete=include_history)
    logger.info("done!")
    return True

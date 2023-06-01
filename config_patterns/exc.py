# -*- coding: utf-8 -*-


class S3BucketVersionSuspendedError(Exception):
    """
    We don't store config files in a bucket with 'suspended' status.
    This exception is raised when we try to deploy or get a config file from
    a bucket with 'suspended' status.
    """

    pass


class S3ObjectNotExist(Exception):
    pass


class ParameterNotExists(Exception):
    pass

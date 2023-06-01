# -*- coding: utf-8 -*-

try: # pragma: no cover
    from .s3 import (
        ZFILL,
        KEY_CONFIG_VERSION,
        KEY_CONFIG_SHA256,
        S3BucketVersionStatus,
        S3Object,
        S3Parameter,
        read_config,
        deploy_config,
        delete_config,
    )
except ImportError as e: # pragma: no cover
    pass

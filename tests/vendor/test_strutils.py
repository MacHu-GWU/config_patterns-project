# -*- coding: utf-8 -*-

from config_patterns.vendor.strutils import (
    slugify, camel2under
)

def test_slugify():
    pass


if __name__ == "__main__":
    from config_patterns.tests import run_cov_test

    run_cov_test(__file__, "config_patterns.vendor.strutils", preview=False)
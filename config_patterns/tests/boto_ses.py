# -*- coding: utf-8 -*-

from boto_session_manager import BotoSesManager

aws_profile = "opensource"

bsm = BotoSesManager(profile_name=aws_profile)

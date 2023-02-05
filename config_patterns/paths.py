# -*- coding: utf-8 -*-

import sys
from pathlib import Path

dir_project_root = Path(__file__).absolute().parent.parent


# # ------------------------------------------------------------------------------
# # Config Management Related
# # ------------------------------------------------------------------------------
# dir_config = dir_project_root / "config"
# path_config_json = dir_config / "config.json"
# path_config_secret_json = dir_home_project_root / "config-secret.json"
# path_current_env_name_json = dir_project_root / ".current-env-name.json"

# ------------------------------------------------------------------------------
# Virtual Environment Related
# ------------------------------------------------------------------------------
dir_venv = Path(sys.executable).parent.parent
dir_venv_bin = dir_venv / "bin"

# virtualenv executable paths
bin_pytest = dir_venv_bin / "pytest"

# test related
dir_htmlcov = dir_project_root / "htmlcov"
path_cov_index_html = dir_htmlcov / "index.html"
dir_unit_test = dir_project_root / "tests"
dir_int_test = dir_project_root / "tests_int"

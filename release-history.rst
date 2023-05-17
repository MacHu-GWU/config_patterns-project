.. _release_history:

Release and Version History
==============================================================================


Backlog (TODO)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

**Minor Improvements**

**Bugfixes**

**Miscellaneous**


1.0.1 (2023-05-17)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Breaking Changes**

- ``1.X.Y`` is not compatible with ``0.X.Y`` at all.
- The config json file schema is completely redesigned to embrace "inheritance hierarchy" and advanced "config merge" features.

**Features and Improvements**

- Allow JSON path notation to apply shared config values.
- Allow merging dict, list of dict, deeply nested dict or list of dict.
- Add a :mod:`~config_patterns.patterns.hierarchy` that implements "inheritance hierarchy" pattern, and can be used independently.
- Add a :mod:`~config_patterns.patterns.merge_key_value.py` that implements "config merge" pattern, and can be used independently.

**Miscellaneous**

- Update the example Jupyter Notebook.


0.4.1 (2023-05-12)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- the :mod:`config_pattern.patterns.multi_env_json` now support deploying to multiple AWS Account with different AWS profiles.

**Minor Improvements**

- refactor the :mod:`config_pattern.patterns.multi_env_json` to make it more maintainable.


0.3.3 (2023-03-19)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Minor Improvements**

- the ``config_pattern.patterns.multi_env_json.BaseConfig.deploy`` method now returns a list of ``config_pattern.patterns.multi_env_json.ConfigDeployment``deployment`` objects.


0.3.2 (2023-02-27)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Minor Improvements**

- improve the error message when the ``config_pattern.patterns.multi_env_json.BaseConfig.get_env`` method failed due to the config definition and config data mismatch.


0.3.1 (2023-02-13)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Minor Improvements**

- now depends on ``pysecret >= 2.2.2``

**Bugfixes**

- fix a bug that the ``bsm`` argument is missing


0.2.2 (2023-02-07)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Bugfixes**

- fix a bug that multi environment json pattern cannot automatically prepend a prefix when project name starts with "aws" or "ssm".


0.2.1 (2023-02-07)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- multi environment json pattern now can delete configs.


0.1.1 (2023-02-04)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- First release.
- add multi environment json pattern.

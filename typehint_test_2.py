# -*- coding: utf-8 -*-

import typing as T
import dataclasses


# ------------------------------------------------------------------------------
# Config Pattern API
# ------------------------------------------------------------------------------
@dataclasses.dataclass
class BaseEnv:
    def base_env_method(self):
        print("base_env_method")


T_BASE_ENV = T.TypeVar("T_BASE_ENV", bound=BaseEnv)


@dataclasses.dataclass
class BaseConfig(T.Generic[T_BASE_ENV]):
    """
    The config class take the env class (not instance) as a parameter.
    Some method will return an instance of the env class.
    """

    env_class: T.Type[T_BASE_ENV] = dataclasses.field()

    def get_env(self, env_name: str) -> T_BASE_ENV:
        return self.env_class()

    @property
    def env(self) -> T_BASE_ENV:
        return self.get_env(env_name="devops")


# ------------------------------------------------------------------------------
# User Extended API
# ------------------------------------------------------------------------------
@dataclasses.dataclass
class MyBaseEnv(BaseEnv):
    def my_base_env_method(self):
        print("my_base_env_method")


T_MY_BASE_ENV = T.TypeVar("T_MY_BASE_ENV", bound=MyBaseEnv)


# 如果你希望这个类在被继承之后使用, 并且自动让基类中的方法 BaseConfig.get_env(), BaseConfig.env
# 的返回值的类型自动被继承之后变化, 就需要用到 TypeVar 和 Generic 的组合.
@dataclasses.dataclass
class MyBaseConfig(BaseConfig[T_MY_BASE_ENV], T.Generic[T_MY_BASE_ENV]):
    pass


# ------------------------------------------------------------------------------
# Multi inherit
# ------------------------------------------------------------------------------
@dataclasses.dataclass
class MyFinalEnv(MyBaseEnv):
    def my_final_env_method(self):
        print("my_final_env_method")


@dataclasses.dataclass
class MyFinalConfig(MyBaseConfig[MyFinalEnv]):
    @property
    def sbx(self):
        return self.get_env(env_name="sbx")


sbx = MyFinalConfig(env_class=MyFinalEnv).get_env("sbx")
sbx.base_env_method()
sbx.my_base_env_method()
sbx.my_final_env_method()

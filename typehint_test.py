# -*- coding: utf-8 -*-

import typing as T
import dataclasses


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

    def env(self) -> T_BASE_ENV:
        return self.env_class()


@dataclasses.dataclass
class MyEnv(BaseEnv):
    def my_env_method(self):
        print("env_method")


@dataclasses.dataclass
class MyConfig(BaseConfig[MyEnv]):
    pass


env = MyConfig(env_class=MyEnv).env()
env.my_env_method()  # can successfully detect my_env_method

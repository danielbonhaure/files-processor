
from typing import Any

from singleton import Singleton
from errors import ConfigError

import os
import yaml


@Singleton
class ConfigFile:

    def __init__(self):
        self._file_name: str = 'config.yaml'
        self.cpt_config: dict = self.__load_config()

    def __load_config(self) -> dict:
        if not os.path.exists(self._file_name):
            raise ConfigError(f"Configuration file (i.e. {self._file_name}) not found!")
        with open(self._file_name, 'r') as f:
            return yaml.safe_load(f)

    @property
    def file_name(self) -> str:
        return self._file_name

    @file_name.setter
    def file_name(self, value: str) -> None:
        self._file_name = value
        self.cpt_config = self.__load_config()

    def get(self, key, default: Any = None) -> Any:
        return self.cpt_config.get(key, default)

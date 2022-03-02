
from errors import ConfigError

from typing import Any

import os
import yaml


class ConfigFile:

    def __init__(self, config_file: str = 'config.yaml'):
        self._file_name: str = config_file
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

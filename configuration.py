
from errors import ConfigError, DescriptorError
from singleton import Singleton

from typing import Any

import os
import yaml


@Singleton
class ConfigFile:

    def __init__(self, config_file: str = 'config.yaml'):
        self._file_name: str = config_file
        self.config: dict = self.__load_config()

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
        self.config = self.__load_config()

    def get(self, key, default: Any = None) -> Any:
        return self.config.get(key, default)


class DescriptorFile:

    def __init__(self, descriptor_file: str):
        self._file_name: str = descriptor_file
        self.descriptor: dict = self.__load_descriptor()

    def __load_descriptor(self) -> dict:
        if not os.path.exists(self._file_name):
            raise DescriptorError(f"Descriptor file (i.e. {self._file_name}) not found!")
        with open(self._file_name, 'r') as f:
            return yaml.safe_load(f)

    @property
    def file_name(self) -> str:
        return self._file_name

    @file_name.setter
    def file_name(self, value: str) -> None:
        self._file_name = value
        self.descriptor = self.__load_descriptor()

    def get(self, key, default: Any = None) -> Any:
        return self.descriptor.get(key, default)

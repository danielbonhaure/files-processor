from errors import ConfigError, DescriptorError
from helpers import MonthsProcessor as Mpro
from helpers import nrange, FilesSearcher
from singleton import Singleton

from typing import Any
from pathlib import Path

import os
import yaml
import logging


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

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any = None):
        self.config[key] = value


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


class DescFilesSelector(object):

    def __init__(self, target_year: int | None, target_month: int | None,
                 skip_ereg: bool = False, skip_pycpt: bool = False):

        # Definir año y mes objetivos
        self.target_year: int | None = target_year
        self.target_month: int | None = target_month
        self.target_month_abbr: str | None = None

        # Se validan target_year y target_month (en caso de ser necesario)
        if target_year is not None and target_month is not None:
            # Verificar argumentos
            if target_month < 1 or target_month > 12:
                raise ValueError('Wrong arguments (target_month must be between 1 and 12)')
            # Obtener abreviatura para el mes objetivo (target_month)
            self.target_month_abbr = Mpro.month_int_to_abbr(target_month)

        # Definir descriptores a ser considerados
        self.skip_ereg: bool = skip_ereg
        self.skip_pycpt: bool = skip_pycpt

        # Obtener la carpeta en la cual se van a buscar los descriptores
        self.target_folder: Path = Path(
            ConfigFile.Instance().get('folders').get('descriptor_files')
        )

    def ereg_output_descriptor_files(self) -> list[Path]:

        # Definir el patrón de búsqueda
        rglob_pattern = '*_descriptors*.yaml'
        if self.target_year is not None and self.target_month_abbr is not None:
            rglob_pattern = f'*_{self.target_month_abbr}{self.target_year}.yaml'
        logging.debug(f'rglob_pattern = {rglob_pattern}')

        # Obtener listado de archivos de configuración y/o descriptores
        desc_files = sorted(self.target_folder.rglob(rglob_pattern))
        desc_files = [f for f in desc_files if f.name != 'template.yaml']

        # Retornar descriptores a ser procesados
        return desc_files

    def pycpt_descriptor_files_months(self) -> list[Path]:

        # Crear lista para almacenar descriptores a procesar
        desc_files: list[Path] = []

        # Crear objeto para filtrar archivos
        yaml_files = sorted(self.target_folder.rglob(f'*.yaml'))
        searcher = FilesSearcher(target_files=yaml_files)

        # 1er caso: cuando no se requiere filtrar por año y mes
        if self.target_year is None and self.target_month is None:

            # Definir el patrón de búsqueda (obs_data/predictands)
            regex_1 = rf'(?:prcp|t2m)_(?:chirps|era5-land)_[1-12].yaml'
            # Definir el patrón de búsqueda (predictors and outputs)
            regex_2 = rf'.*_(?:{"|".join(Mpro.trimesters[1:])})ic_[1-12]_.*_\d{4}_1.yaml'
            # Seleccionar archivos
            desc_files.extend(searcher.filter_files([regex_1, regex_2]))

        # 2do caso: cuando sí se requiere filtrar por año y mes
        if self.target_year is not None and self.target_month is not None:

            # Definir meses objetivo
            start = 1 if self.target_month == 12 else self.target_month + 1
            fcst_months = [month for month in nrange(start, 6, 12)]
            # Buscar descriptores para los distintos leadtimes (pronos mensuales)
            for fcst_month in fcst_months:
                # Definir el patrón de búsqueda (obs_data/predictands)
                regex_1 = rf'(?:prcp|t2m)_(?:chirps|era5-land)_{fcst_month}.yaml'
                # Definir año correspondiente a fcst_month
                fcst_year = self.target_year
                if self.target_month > fcst_month:
                    fcst_year = self.target_year + 1
                # Definir el patrón de búsqueda (predictors and outputs)
                regex_2 = rf'.*_{self.target_month_abbr}ic_{fcst_month}_.*_{fcst_year}_1.yaml'
                # Seleccionar archivos
                desc_files.extend(searcher.filter_files([regex_1, regex_2]))

        # Para garantizar que no se procese el archivo template.yaml
        desc_files = [f for f in desc_files if f.name != 'template.yaml']

        # Retornar descriptores a ser procesados
        return desc_files

    def pycpt_descriptor_files_trimesters(self) -> list[Path]:

        # Crear lista para almacenar descriptores a procesar
        desc_files: list[Path] = []

        # Crear objeto para filtrar archivos
        yaml_files = sorted(self.target_folder.rglob(f'*.yaml'))
        searcher = FilesSearcher(target_files=yaml_files)

        # 1er caso: cuando no se requiere filtrar por año y mes
        if self.target_year is None and self.target_month is None:

            # Definir el patrón de búsqueda (obs_data/predictands)
            regex_1 = rf'(?:prcp|t2m)_(?:chirps|era5-land)_[1-12]-[1-12].yaml'
            # Definir el patrón de búsqueda (predictors and outputs)
            regex_2 = rf'.*_(?:{"|".join(Mpro.trimesters[1:])})ic_[1-12]-[1-12]_.*_\d{4}-\d{4}_1.yaml'
            # Seleccionar archivos
            desc_files.extend(searcher.filter_files([regex_1, regex_2]))

        # 2do caso: cuando sí se requiere filtrar por año y mes
        if self.target_year is not None and self.target_month is not None:

            # Definir meses de inicio de los trimestres objetivo
            start = 1 if self.target_month == 12 else self.target_month + 1
            first_fcst_months = [month for month in nrange(start, 6, 12)]

            # Buscar descriptores para los distintos leadtimes (pronos trimestrales)
            for first_fcst_month in first_fcst_months:
                last_fcst_month = Mpro.add_months(first_fcst_month, 2)
                # Definir el patrón de búsqueda (obs_data/predictands)
                regex_1 = rf'(?:prcp|t2m)_(?:chirps|era5-land)_{first_fcst_month}-{last_fcst_month}.yaml'
                # Definir año correspondiente a first_fcst_year
                first_fcst_year = self.target_year + 1 if self.target_month > first_fcst_month else self.target_year
                # Definir año correspondiente a last_fcst_year
                last_fcst_year = self.target_year + 1 if self.target_month > last_fcst_month else self.target_year
                # Definir el patrón de búsqueda (predictors and outputs)
                regex_2 = rf'.*_{self.target_month_abbr}ic_{first_fcst_month}-{last_fcst_month}_'\
                          rf'.*_{first_fcst_year}-{last_fcst_year}_1.yaml'
                # Seleccionar archivos
                desc_files.extend(searcher.filter_files([regex_1, regex_2]))

        # Para garantizar que no se procese el archivo template.yaml
        desc_files = [f for f in desc_files if f.name != 'template.yaml']

        # Retornar descriptores a ser procesados
        return desc_files

    @property
    def target_descriptors(self) -> list[Path]:

        # Obtener descriptores
        ereg_desc = [] if self.skip_ereg else self.ereg_output_descriptor_files()
        pycpt_desc_1 = [] if self.skip_pycpt else self.pycpt_descriptor_files_months()
        pycpt_desc_2 = [] if self.skip_pycpt else self.pycpt_descriptor_files_trimesters()

        # Retornar descriptores
        return ereg_desc + pycpt_desc_1 + pycpt_desc_2


from contextlib import contextmanager
from itertools import chain, repeat
from dataclasses import dataclass
from pathlib import Path
from typing import Union
from datetime import datetime
from typing import List

import locale
import calendar
import re


@contextmanager
def localized(new_locale: str):
    original_locale = '.'.join(
        p for p in locale.getlocale() if p)
    if new_locale == original_locale:
        yield
    else:
        locale.setlocale(locale.LC_ALL, new_locale)
        yield
        locale.setlocale(locale.LC_ALL, original_locale)


def crange(start: int, stop: int, modulo: int):
    # Verificar argumentos
    if start > modulo:
        raise ValueError('Wrong arguments (start cannot be greater than modulo)')
    if stop > modulo+1:
        raise ValueError('Wrong arguments (stop cannot be greater than modulo+1)')
    # Ejecutar función
    if start > stop:
        return chain(range(start, modulo+1), range(1, stop))
    else:
        return range(start, stop)


def nrange(start: int, n_steps: int, modulo: int):
    # Verificar argumentos
    if start > modulo:
        raise ValueError('Wrong arguments (start cannot be greater than modulo)')
    # Ejecutar función
    values, last_value = [start], start
    for _ in repeat(None, n_steps-1):
        last_value = last_value + 1
        if last_value > 12:
            last_value = last_value - 12
        values = values + [last_value]
    return values


class MonthsProcessor(object):

    with localized("en_US.UTF-8"):
        months_abbr = list(calendar.month_abbr)

    with localized("en_US.UTF-8"):
        months_names = list(calendar.month_name)

    # OBS: los índices indican el mes inicial de cada trimestre!!
    trimesters = ['', 'JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ', 'DJF']

    @classmethod
    def month_abbr_to_int(cls, month: str) -> int:
        return cls.months_abbr.index(month)

    @classmethod
    def month_int_to_abbr(cls, month: int) -> str:
        return cls.months_abbr[month]

    @classmethod
    def add_months(cls, month: int, months_to_add: int):
        result = (month + months_to_add) % 12
        return result if result != 0 else 12

    @classmethod
    def first_month_of_trimester(cls, trimester: str) -> int:
        try:
            return cls.trimesters.index(trimester)
        except ValueError:
            raise ValueError(f"Trimestre inválido: {trimester}")

    @classmethod
    def n_days_in_trimester(cls, trimester: str, isleap: bool = False) -> int:
        first_month = cls.first_month_of_trimester(trimester)
        months = nrange(first_month, 3, 12)
        days_to_add = 1 if isleap and 2 in months else 0
        return sum(calendar.mdays[m] for m in months) + days_to_add

    @classmethod
    def n_days_in_months(cls, fcst_year: int, fcst_month: int, trgt_months: List[int]) -> int:
        n_days = 0
        for c_month in trgt_months:
            n_days += calendar.monthrange(fcst_year if fcst_month <= c_month else fcst_year+1, c_month)[1]
        return n_days


@dataclass
class CPToutputFileInfo(object):
    n_rows: int
    n_cols: int
    na_values: Union[int, float, str]
    header_line: int
    data_first_line: int
    field_n_rows: int
    header_n_rows: int


@dataclass
class CPTpredictorFileInfo(object):
    n_rows: int
    n_cols: int
    na_values: Union[int, float, str]
    field_line: int
    start_date: datetime
    target_first_month_date: datetime
    target_last_month_date: datetime


class FilesSearcher(object):

    def __init__(self, target_files: list[Path]):
        self.target_files: list[Path] = target_files

    def filter_files(self, search_patterns: list[str]) -> list[Path]:

        # Crear lista para almacenar los archivos seleccionados
        desc_files: list[Path] = []

        # Iterar sobre los patrones de búsqueda recibidos y seleccionar archivos
        for regex in search_patterns:
            pattern = re.compile(regex)  # compilar el patrón de búsqueda
            c_desc_files = [p for p in self.target_files if p.is_file() and pattern.search(p.name)]
            desc_files.extend(c_desc_files)  # Almacenar archivos seleccionados

        # Retornar archivos que cumplen con los patrónes de búsqueda
        return desc_files

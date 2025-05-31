
from contextlib import contextmanager
from itertools import chain, repeat
from dataclasses import dataclass
from typing import Union
from datetime import datetime
from typing import List

import locale
import calendar


@contextmanager
def localized(new_locale):
    original_locale = '.'.join(locale.getlocale())
    if new_locale == original_locale:
        yield
    else:
        locale.setlocale(locale.LC_ALL, new_locale)
        yield
        locale.setlocale(locale.LC_ALL, original_locale)


def crange(start, stop, modulo):
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


def nrange(start, n_steps, modulo):
    # Verificar argumentos
    if start > modulo:
        raise ValueError('Wrong arguments (start cannot be greater than modulo)')
    # Ejecutar función
    values, last_value = [start], start
    for _ in repeat(None, n_steps): # Cycles n_steps times
        last_value = last_value + 1
        if last_value > 12:
            last_value = last_value - 12
        values = values + [last_value]
    return values


class MonthsProcessor:

    with localized("en_US.UTF-8"):
        months_abbr = list(calendar.month_abbr)

    with localized("en_US.UTF-8"):
        months_names = list(calendar.month_name)

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
    def n_days_in_trimester(cls, trimester: str, isleap: bool = False) -> int:
        if trimester == 'JFM':
            return calendar.mdays[1] + calendar.mdays[2] + calendar.mdays[3] + 1 if isleap else 0
        elif trimester == 'FMA':
            return calendar.mdays[2] + calendar.mdays[3] + calendar.mdays[4] + 1 if isleap else 0
        elif trimester == 'MAM':
            return calendar.mdays[3] + calendar.mdays[4] + calendar.mdays[5]
        elif trimester == 'AMJ':
            return calendar.mdays[4] + calendar.mdays[5] + calendar.mdays[6]
        elif trimester == 'MJJ':
            return calendar.mdays[5] + calendar.mdays[6] + calendar.mdays[7]
        elif trimester == 'JJA':
            return calendar.mdays[6] + calendar.mdays[7] + calendar.mdays[8]
        elif trimester == 'JAS':
            return calendar.mdays[7] + calendar.mdays[8] + calendar.mdays[9]
        elif trimester == 'ASO':
            return calendar.mdays[8] + calendar.mdays[9] + calendar.mdays[10]
        elif trimester == 'SON':
            return calendar.mdays[9] + calendar.mdays[10] + calendar.mdays[11]
        elif trimester == 'OND':
            return calendar.mdays[10] + calendar.mdays[11] + calendar.mdays[12]
        elif trimester == 'NDJ':
            return calendar.mdays[11] + calendar.mdays[12] + calendar.mdays[1]
        elif trimester == 'DJF':
            return calendar.mdays[12] + calendar.mdays[1] + calendar.mdays[2] + 1 if isleap else 0
        return 0

    @classmethod
    def first_month_of_trimester(cls, trimester: str) -> int:
        if trimester == 'JFM':
            return 1
        elif trimester == 'FMA':
            return 2
        elif trimester == 'MAM':
            return 3
        elif trimester == 'AMJ':
            return 4
        elif trimester == 'MJJ':
            return 5
        elif trimester == 'JJA':
            return 6
        elif trimester == 'JAS':
            return 7
        elif trimester == 'ASO':
            return 8
        elif trimester == 'SON':
            return 9
        elif trimester == 'OND':
            return 10
        elif trimester == 'NDJ':
            return 11
        elif trimester == 'DJF':
            return 12
        return 0

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

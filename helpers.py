
from contextlib import contextmanager
from itertools import chain
from dataclasses import dataclass
from typing import Union
from datetime import datetime

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
    if start > stop:
        return chain(range(start, modulo+1), range(1, stop))
    else:
        return range(start, stop)


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

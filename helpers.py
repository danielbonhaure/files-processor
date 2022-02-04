
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

    @classmethod
    def month_abbr_to_int(cls, month: str) -> int:
        return cls.months_abbr.index(month)

    @classmethod
    def month_int_to_abbr(cls, month: int) -> str:
        return cls.months_abbr[month]


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


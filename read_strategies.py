
from __future__ import annotations

import os.path
from abc import ABC, abstractmethod
from typing import List

from xarray import Dataset
from pandas import DataFrame
from datetime import datetime

from helpers import CPToutputFileInfo, CPTpredictorFileInfo
from helpers import MonthsProcessor as Mpro

import re
import os.path
import pandas as pd
import numpy as np
import xarray as xr


""" 
Año inicial a ser utilizado cuando se requiere una fecha y no se puede determinar el año
"""
DEFAULT_START_YEAR = 1900


class FileReader(object):
    """
    The Context (Desing Pattern -> Strategy)
    """

    def __init__(self, strategy: ReadStrategy) -> None:
        self._read_strategy = strategy

    @property
    def read_strategy(self) -> ReadStrategy:
        return self._read_strategy

    @read_strategy.setter
    def read_strategy(self, strategy: ReadStrategy) -> None:
        self._read_strategy = strategy

    def read_file(self, file_name: str, file_config: dict = None) -> Dataset:
        # Leer los datos en el archivo (en un dataframe)
        final_df = self._read_strategy.read_data(file_name, file_config).to_dataframe()

        # Filtrar años, en caso de que sea necesario
        if file_config is not None and file_config.get('filter_years') is not None:
            min_year = file_config.get('filter_years').get('min_year')
            if min_year is not None:
                final_df = final_df.loc[final_df.index.get_level_values('time').year >= min_year]
            max_year = file_config.get('filter_years').get('max_year')
            if max_year is not None:
                final_df = final_df.loc[final_df.index.get_level_values('time').year <= max_year]

        # Retornar el df con los datos leídos del archivo
        return final_df.to_xarray()

    def convert_file_to_netcdf(self, file_name: str, file_config: dict = None) -> None:
        # Definir el nombre del archivo NetCDF
        output_file_name = f"{os.path.splitext(file_name)[0]}.nc"
        if file_config is not None and file_config.get('output_file') is not None:
            output_path = file_config.get('output_file').get('path', os.path.dirname(output_file_name))
            output_file = file_config.get('output_file').get('name', os.path.basename(output_file_name))
            output_file_name = os.path.join(output_path, output_file)

        # Convertir pandas dataframe a xarray dataset
        with self.read_file(file_name, file_config) as ds:
            # Guardar el dataset en un NetCDF
            ds.to_netcdf(output_file_name)


class ReadStrategy(ABC):
    """
    The Strategy Interface (Desing Pattern -> Strategy)
    """
    @abstractmethod
    def read_data(self, file_name: str, file_config: dict = None) -> Dataset:
        pass


class ReadCPToutputDET(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, file_config: dict = None) -> Dataset:
        # Extraer información del archivo CPT
        info: CPToutputFileInfo = self.__extract_cpt_output_file_info(file_name)

        # Identificar el mes de corrida en el nombre del archivo
        forecast_month = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)ic', file_name).group(1)
        forecast_month = Mpro.month_abbr_to_int(forecast_month)

        # Identificar la variable en el nombre del archivo
        file_variable = re.search(r'(prcp|t2m)', file_name).group(0)

        # Obtener el nombre de las columnas, las longitude y las latitudes
        header_df = pd.read_csv(file_name, sep='\t', header=0, index_col=0,
                                skiprows=info.header_line, nrows=2, na_values=info.na_values)

        # En los archivos de salida del CPT:
        # la línea que empieza con cpt:X es la longitud, y la línea que empieza con cpt:Y es la latitud
        header_df.rename(index={'cpt:X': 'longitude', 'cpt:Y': 'latitude'}, inplace=True)

        # Crear un dataframe con longitud y latitude (e índice igual al nombre de las columnas en data_df)
        longitude_df = pd.DataFrame({'longitude': header_df.loc['longitude']})
        latitude_df = pd.DataFrame({'latitude': header_df.loc['latitude']})
        coord_data_df = longitude_df.join(latitude_df)

        # Obtener los datos en el archivo
        data_df = pd.read_csv(file_name, sep='\t', names=header_df.columns.to_list(), index_col=0,
                              skiprows=info.data_first_line, nrows=info.n_rows, na_values=info.na_values)

        # Crear df con índice igual a longitude, latitude, year
        final_df = pd.DataFrame()
        for year in data_df.index.to_list():
            year_data_df = pd.DataFrame({file_variable: data_df.loc[year]})
            year_data_df = coord_data_df.join(year_data_df)
            year_data_df.insert(2, 'time', pd.to_datetime(f'{year}-{forecast_month}-01'))
            final_df = pd.concat([final_df, year_data_df])

        # Modificar años, en caso de que sea necesario
        if file_config is not None and file_config.get('swap_years') is not None:

            # Obtener último año de hindcast y primer año pronosticado
            last_hindcast_year = file_config.get('swap_years').get('last_hindcast_year')
            first_forecast_year = file_config.get('swap_years').get('first_forecast_year')

            # Identificar los años posteriores al último año de hindcast, todos estos años deben ser renombrados
            years_to_swap = set([y for y in final_df['time'].dt.year if y > last_hindcast_year])

            # Se crea un dataframe con los años renombrados
            anhos_renombrados = pd.DataFrame()

            # Recorrer los años que deben ser renombrados, "y" es el año a ser modificado y "n" es la
            # cantidad que debe sumarse al primer año pronosticado para obtener el año final.
            for n, y in enumerate(years_to_swap):
                # Se hace una copia profunda del año a renombrar
                aux = final_df.loc[final_df['time'].dt.year == y].copy(deep=True)
                # Se actualiza el año en el dataframe auxiliar (que contiene un solo año)
                aux['time'] = aux['time'].apply(lambda x: x.replace(year=first_forecast_year+n))
                # Se agrega el dataframe aux al df con los años renombrados
                anhos_renombrados = pd.concat([anhos_renombrados, aux])
                # Se asgina NA al año que ya fue renombrado
                final_df.loc[final_df['time'].dt.year == y, file_variable] = np.nan

            # Se reemplaza los valores con NA en final_df con los valores corregidos
            final_df = final_df.merge(anhos_renombrados, how='outer')

        # Reindexar el dataframe
        final_df = final_df.set_index(['time', 'latitude', 'longitude']).sort_index()

        # Transformar dataframe a dataset
        final_ds = final_df.to_xarray()

        # Agregar atributos que describan la variable
        unidad_de_medida = 'mm' if file_variable == 'prcp' else 'Celsius' if file_variable == 't2m' else None
        final_ds[file_variable].attrs['units'] = f'{unidad_de_medida}'

        # Return generated dataset
        return final_ds

    @staticmethod
    def __extract_cpt_output_file_info(file_name: str) -> CPToutputFileInfo:
        # Abrir el archivo
        with open(file_name) as fp:
            # Leer el archivo línea por línea
            for cnt, line in enumerate(fp):
                # Aplicar expresiones regulares a la línea actual
                n_rows_regex, n_cols_regex = re.search(r'cpt:nrow=(\d+),', line), re.search(r'cpt:ncol=(\d+),', line)
                na_values_regex = re.search(r'cpt:missing=([-+]?\d+\.?\d+?)', line)
                # La línea con los datos buscados cumple con las 3 expresiones regulares
                if n_rows_regex and n_cols_regex and na_values_regex:
                    # Extraer los datos del archivo
                    n_rows, n_cols = int(n_rows_regex.group(1)), int(n_cols_regex.group(1))
                    na_values = float(na_values_regex.group(1))
                    header_line, data_first_line = cnt + 1, cnt + 4
                    header_n_rows = data_first_line - header_line
                    # Retornar los datos del archivo
                    return CPToutputFileInfo(n_rows, n_cols, na_values, header_line, data_first_line, 1, header_n_rows)


class ReadCPToutputPROB(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, file_config: dict = None) -> Dataset:
        # Extraer información del archivo CPT
        info: CPToutputFileInfo = self.__extract_cpt_output_file_info(file_name)

        # Identificar el mes de corrida en el nombre del archivo
        forecast_month = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)ic', file_name).group(1)
        forecast_month = Mpro.month_abbr_to_int(forecast_month)

        # Identificar la variable en el nombre del archivo
        file_variable = re.search(r'(prcp|t2m)', file_name).group(0)

        # Obtener el nombre de las columnas, las longitude y las latitudes
        header_df = pd.read_csv(file_name, sep='\t', header=0, index_col=0,
                                skiprows=info.header_line, nrows=2, na_values=info.na_values)

        # En los archivos de salida del CPT:
        # la línea que empieza con cpt:X es la longitud, y la línea que empieza con cpt:Y es la latitud
        header_df.rename(index={'cpt:X': 'longitude', 'cpt:Y': 'latitude'}, inplace=True)

        # Crear un dataframe con longitud y latitude (e índice igual al nombre de las columnas en data_df)
        longitude_df = pd.DataFrame({'longitude': header_df.loc['longitude']})
        latitude_df = pd.DataFrame({'latitude': header_df.loc['latitude']})
        coord_data_df = longitude_df.join(latitude_df)

        # Obtener los datos en el archivo
        final_df = pd.DataFrame()
        for i, category in enumerate(['below', 'normal', 'above']):
            skip_rows = info.data_first_line + (info.field_n_rows * i) + (info.header_n_rows * i) + (info.n_rows * i)
            cat_data_df = pd.read_csv(file_name, sep='\t', names=header_df.columns.to_list(), index_col=0,
                                      skiprows=skip_rows, nrows=info.n_rows, na_values=info.na_values)
            category_df = pd.DataFrame()
            for year in cat_data_df.index.to_list():
                year_data_df = pd.DataFrame({file_variable: cat_data_df.loc[year]})
                year_data_df = coord_data_df.join(year_data_df)
                year_data_df.insert(2, 'time', pd.to_datetime(f'{year}-{forecast_month}-01'))
                year_data_df.insert(3, 'category', category)
                category_df = pd.concat([category_df, year_data_df])
            final_df = pd.concat([final_df, category_df])

        # Modificar años, en caso de que sea necesario
        if file_config is not None and file_config.get('swap_years') is not None:

            # Obtener último año de hindcast y primer año pronosticado
            last_hindcast_year = file_config.get('swap_years').get('last_hindcast_year')
            first_forecast_year = file_config.get('swap_years').get('first_forecast_year')

            # Identificar los años posteriores al último año de hindcast, todos estos años deben ser renombrados
            years_to_swap = set([y for y in final_df['time'].dt.year if y > last_hindcast_year])

            # Se crea un dataframe con los años renombrados
            anhos_renombrados = pd.DataFrame()

            # Recorrer los años que deben ser renombrados, "y" es el año a ser modificado y "n" es la
            # cantidad que debe sumarse al primer año pronosticado para obtener el año final.
            for n, y in enumerate(years_to_swap):
                # Se hace una copia profunda del año a renombrar
                aux = final_df.loc[final_df['time'].dt.year == y].copy(deep=True)
                # Se actualiza el año en el dataframe auxiliar (que contiene un solo año)
                aux['time'] = aux['time'].apply(lambda x: x.replace(year=first_forecast_year+n))
                # Se agrega el dataframe aux al df con los años renombrados
                anhos_renombrados = pd.concat([anhos_renombrados, aux])
                # Se asgina NA al año que ya fue renombrado
                final_df.loc[final_df['time'].dt.year == y, file_variable] = np.nan

            # Se reemplaza los valores con NA en final_df con los valores corregidos
            final_df = final_df.merge(anhos_renombrados, how='outer')

        # Definir la categoría como una categoría, entonces el ordenar toma el orden
        # declarado en lugar de ordenar la categoría por orden alfabético.
        final_df['category'] = final_df['category'].astype('category')
        final_df['category'] = final_df['category'].cat.set_categories(['below', 'normal', 'above'])
        # Reindexar el dataframe
        final_df = final_df.set_index(['time', 'latitude', 'longitude', 'category']).sort_index()

        # Transformar dataframe a dataset
        final_ds = final_df.to_xarray()

        # Agregar atributos que describan la variable
        final_ds[file_variable].attrs['units'] = '%'

        # Return generated dataset
        return final_ds

    @staticmethod
    def __extract_cpt_output_file_info(file_name: str) -> CPToutputFileInfo:
        # Abrir el archivo
        with open(file_name) as fp:
            # Leer el archivo línea por línea
            for cnt, line in enumerate(fp):
                # Aplicar expresiones regulares a la línea actual
                n_rows_regex, n_cols_regex = re.search(r'cpt:nrow=(\d+),', line), re.search(r'cpt:ncol=(\d+),', line)
                na_values_regex = re.search(r'cpt:missing=([-+]?\d+\.?\d+?)', line)
                # La línea con los datos buscados cumple con las 3 expresiones regulares
                if n_rows_regex and n_cols_regex and na_values_regex:
                    # Extraer los datos del archivo
                    n_rows, n_cols = int(n_rows_regex.group(1)), int(n_cols_regex.group(1))
                    na_values = float(na_values_regex.group(1))
                    header_line, data_first_line = cnt + 1, cnt + 4
                    header_n_rows = data_first_line - header_line
                    # Retornar los datos del archivo
                    return CPToutputFileInfo(n_rows, n_cols, na_values, header_line, data_first_line, 1, header_n_rows)


class ReadCPTpredictand(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, file_config: dict = None) -> Dataset:
        # Identificar el mes de corrida en el nombre del archivo
        month_regex = re.search(r'_(\d+)-?(\d+)?\.txt', file_name)
        first_month, last_month = month_regex.group(1), month_regex.group(2)

        # Identificar la variable en el nombre del archivo
        file_variable = re.search(r'(prcp|t2m)', file_name).group(0)

        # Obtener el nombre de las columnas, las longitude y las latitudes
        header_df = pd.read_csv(file_name, sep='\t', header=0, index_col=0, nrows=2)

        # En los archivos de salida del CPT:
        # la línea que empieza con cpt:X es la longitud, y la línea que empieza con cpt:Y es la latitud
        header_df.rename(index={'Lon': 'longitude', 'Lat': 'latitude'}, inplace=True)

        # Crear un dataframe con longitud y latitude (e índice igual al nombre de las columnas en data_df)
        longitude_df = pd.DataFrame({'longitude': header_df.loc['longitude']})
        latitude_df = pd.DataFrame({'latitude': header_df.loc['latitude']})
        coord_data_df = longitude_df.join(latitude_df)

        # Obtener los datos en el archivo
        data_df = pd.read_csv(file_name, sep='\t', names=header_df.columns.to_list(), index_col=0, skiprows=3)

        # Crear df con índice igual a longitude, latitude, year
        final_df = pd.DataFrame()
        for year in data_df.index.to_list():
            year_data_df = pd.DataFrame({file_variable: data_df.loc[year]})
            year_data_df = coord_data_df.join(year_data_df)
            year_data_df.insert(2, 'time', pd.to_datetime(f'{year}-{first_month}-01'))
            final_df = pd.concat([final_df, year_data_df])

        # Reindexar el dataframe
        final_df = final_df.set_index(['time', 'latitude', 'longitude']).sort_index()

        # Transformar dataframe a dataset
        final_ds = final_df.to_xarray()

        # Agregar atributos que describan la variable
        unidad_de_medida = 'mm' if file_variable == 'prcp' else 'Celsius' if file_variable == 't2m' else None
        final_ds[file_variable].attrs['units'] = f'{unidad_de_medida}'

        # Return generated dataset
        return final_ds


class ReadCPTpredictor(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, file_config: dict = None) -> Dataset:
        # Extraer información del archivo CPT
        df_info: List[CPTpredictorFileInfo] = self.__extract_cpt_predictor_file_info(file_name)

        # Identificar la variable en el nombre del archivo
        file_variable = re.search(r'(precip|tmp2m)', file_name).group(0)
        file_variable = 'prcp' if file_variable == 'precip' else 't2m' if file_variable == 'tmp2m' else None

        # Gen dataframe for current file accessing only rows with data
        final_df = pd.DataFrame()
        for info in df_info:
            df = pd.read_csv(file_name, sep='\t', index_col=0, skiprows=info.field_line,
                             nrows=info.n_rows, na_values='-999')
            df['latitude'] = df.index
            df = df.melt(id_vars=['latitude'], var_name='longitude', value_name=file_variable)
            df['longitude'] = df['longitude'].astype(float)
            df.insert(0, 'time', info.start_date)
            final_df = pd.concat([final_df, df])

        # Reindexar el dataframe
        final_df = final_df.set_index(['time', 'latitude', 'longitude']).sort_index()

        # Transformar dataframe a dataset
        final_ds = final_df.to_xarray()

        # Agregar atributos que describan la variable
        unidad_de_medida = 'mm' if file_variable == 'prcp' else 'Celsius' if file_variable == 't2m' else None
        final_ds[file_variable].attrs['units'] = f'{unidad_de_medida}'

        # Return generated dataset
        return final_ds

    @staticmethod
    def __extract_cpt_predictor_file_info(file_name: str) -> List[CPTpredictorFileInfo]:
        df_info: List[CPTpredictorFileInfo] = list()
        # Abrir el archivo
        with open(file_name) as fp:
            # Leer el archivo línea por línea
            for cnt, line in enumerate(fp):

                # Aplicar expresiones regulares a la línea actual
                start_date_regex = re.search(r'cpt:S=(\d+)-(\d+)-(\d+),', line)
                target_date_regex = re.search(r'cpt:T=(\d+)-(\d+)/?(\d+)?-?(\d+)?,', line)
                n_rows_regex, n_cols_regex = re.search(r'cpt:nrow=(\d+),', line), re.search(r'cpt:ncol=(\d+),', line)
                na_values_regex = re.search(r'cpt:missing=([-+]?\d+\.?\d+?)', line)

                # La línea con los datos buscados cumple con las 3 expresiones regulares
                if start_date_regex and target_date_regex and n_rows_regex and n_cols_regex and na_values_regex:

                    # Extraer los datos del archivo
                    n_rows, n_cols, field_line = int(n_rows_regex.group(1)), int(n_cols_regex.group(1)), cnt + 1
                    na_values = float(na_values_regex.group(1))
                    start_date = datetime(
                        int(start_date_regex.group(1)), int(start_date_regex.group(2)), int(start_date_regex.group(3)))
                    target_first_month_date = datetime(
                        int(target_date_regex.group(1)), int(target_date_regex.group(2)), 1)
                    target_last_month_date = None
                    if target_date_regex.group(3) and not target_date_regex.group(4):
                        target_last_month_date = datetime(
                            int(target_date_regex.group(1)), int(target_date_regex.group(3)), 1)
                    if target_date_regex.group(3) and target_date_regex.group(4):
                        target_last_month_date = datetime(
                            int(target_date_regex.group(3)), int(target_date_regex.group(4)), 1)

                    # Retornar los datos del archivo
                    df_info.append(
                        CPTpredictorFileInfo(
                            n_rows, n_cols, na_values, field_line, start_date, target_first_month_date,
                            target_last_month_date))

        # Retornar los datos del archivo
        return df_info


class ReadEREGoutputDET(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, file_config: dict = None) -> Dataset:
        # Identificar el mes de corrida en el nombre del archivo
        forecast_month = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', file_name).group(0)
        forecast_month = Mpro.month_abbr_to_int(forecast_month)

        # Identificar la variable en el nombre del archivo
        file_variable = re.search(r'(prec|tref)', file_name).group(0)
        file_variable = 'prcp' if file_variable == 'prec' else 't2m' if file_variable == 'tref' else None

        # Extraer de la configuración el primer año en el archivo
        first_year = file_config.get('first_year_in_file', DEFAULT_START_YEAR) \
            if file_config is not None else DEFAULT_START_YEAR

        # Leer archivo de tipo npz
        with np.load(file_name) as npz:
            # Identificar variable con datos
            data_variable = [x for x in npz.files if x not in ['lat', 'lon']][0]
            # Identificar la cantidad de años en el archivo
            n_years = len(npz[data_variable])
            # Crear dataset con los datos
            final_ds = xr.Dataset(
                {file_variable: (['time', 'latitude', 'longitude'], np.squeeze(npz[data_variable][:, :, :]))},
                coords={
                    'time': pd.date_range(f"{first_year}-{forecast_month}-01", periods=n_years, freq='12MS'),
                    'latitude': npz['lat'],
                    'longitude': npz['lon']
                }
            )

        # Agregar atributos que describan la variable
        unidad_de_medida = 'mm' if file_variable == 'prcp' else 'Celsius' if file_variable == 't2m' else None
        final_ds[file_variable].attrs['units'] = f'{unidad_de_medida} anomaly'

        # Return generated dataset
        return final_ds


class ReadEREGoutputPROB(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, file_config: dict = None) -> Dataset:
        # Identificar el mes de corrida en el nombre del archivo
        forecast_month = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', file_name).group(0)
        forecast_month = Mpro.month_abbr_to_int(forecast_month)

        # Identificar la variable en el nombre del archivo
        file_variable = re.search(r'(prec|tref)', file_name).group(0)
        file_variable = 'prcp' if file_variable == 'prec' else 't2m' if file_variable == 'tref' else None

        # Extraer de la configuración el primer año en el archivo
        first_year = file_config.get('first_year_in_file', DEFAULT_START_YEAR) \
            if file_config is not None else DEFAULT_START_YEAR

        # Leer archivo de tipo npz
        with np.load(file_name) as npz:
            # Identificar variable con datos
            data_variable = [x for x in npz.files if x not in ['lat', 'lon']][0]
            # Identificar la cantidad de años en el archivo
            n_years = len(npz[data_variable][0])

            # Nombre de dimensiones: ['category', 'time', 'latitude', 'longitude']
            for_terciles = np.squeeze(npz[data_variable][:, :, :, :])

            # Se extraen las probabilidades en el archivo npz
            below = for_terciles[0, :, :, :]
            near = for_terciles[1, :, :, :]
            # Se calcula la probabilidad de un evento superior a la media
            above = 1 - near  # TODO: preguntar a Mechi si esto es correcto
            near = near - below  # TODO: preguntar a Mechi si esto es correcto

            # Se crea la matriz con la que se creará el dataset
            for_terciles = np.concatenate([below[:, :, :, np.newaxis], near[:, :, :, np.newaxis],
                                           above[:, :, :, np.newaxis]], axis=3)

            # Crear dataset con los datos
            final_ds = xr.Dataset(
                {file_variable: (['time', 'latitude', 'longitude', 'category'], for_terciles)},
                coords={
                    'time': pd.date_range(f"{first_year}-{forecast_month}-01", periods=n_years, freq='12MS'),
                    'latitude': npz['lat'],
                    'longitude': npz['lon'],
                    'category': ['below', 'normal', 'above']
                }
            )

        # Agregar atributos que describan la variable
        final_ds[file_variable].attrs['units'] = '%'

        # Return generated dataset
        return final_ds


class ReadCRCSASobs(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, file_config: dict = None) -> Dataset:

        # Identificar la variable en el nombre del archivo
        file_variable = re.search(r'(prcp|t2m)', file_name).group(0)

        # El archivo es un csv, así que solo se importa con pandas y listo
        final_df = pd.read_csv(file_name, sep=';')

        # Reindexar el dataframe
        final_df = final_df.set_index(['time', 'latitude', 'longitude']).sort_index()

        # Transformar dataframe a dataset
        final_ds = final_df.to_xarray()

        # Agregar atributos que describan la variable
        unidad_de_medida = 'mm' if file_variable == 'prcp' else 'Celsius' if file_variable == 't2m' else None
        final_ds[file_variable].attrs['units'] = f'{unidad_de_medida}'

        # Return generated dataset
        return final_ds

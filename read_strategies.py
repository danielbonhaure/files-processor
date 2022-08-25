
from __future__ import annotations

from configuration import ConfigFile
from helpers import CPToutputFileInfo, CPTpredictorFileInfo
from helpers import MonthsProcessor as Mpro

from abc import ABC, abstractmethod
from typing import List

from xarray import Dataset
from datetime import datetime
from pathlib import Path

import re
import os
import pandas as pd
import numpy as np
import xarray as xr
import calendar


""" 
Año inicial a ser utilizado cuando se requiere una fecha y no se puede determinar el año
"""
DEFAULT_START_YEAR = 1900


class FileReader(object):
    """
    The Context (Desing Pattern -> Strategy)
    """

    def __init__(self, strategy: ReadStrategy, desc_file: Path) -> None:
        self._read_strategy = strategy
        self._descriptor_file = desc_file

    @property
    def read_strategy(self) -> ReadStrategy:
        return self._read_strategy

    @read_strategy.setter
    def read_strategy(self, strategy: ReadStrategy) -> None:
        self._read_strategy = strategy

    def define_input_filename(self, desc_file: dict):
        # Definir carpeta del archivo a leer
        desc_file_path = desc_file.get('path')
        if desc_file_path == '.':
            desc_file_path = self._descriptor_file.parent.absolute().as_posix()
        # Definir nombre del archivo a leer
        input_filename = os.path.join(desc_file_path, desc_file.get('name'))
        # Si el path no es absoluto, anteponer la carpeta con los descriptores
        if not os.path.isabs(input_filename):
            input_filename = os.path.join(ConfigFile.Instance().get('folders').get('descriptor_files'), input_filename)
        # Retornar el nombre del archivo a leer
        return input_filename

    def define_output_filename(self, desc_file: dict = None) -> str:
        # Definir nombre del archivo a leer
        input_filename = self.define_input_filename(desc_file)
        # Definir el nombre del archivo NetCDF (para los casos en los que no se defina output_file)
        output_filename = f"{os.path.splitext(input_filename)[0]}.nc"
        # Definir el nombre del archivo NetCDF (para los casos en los que sí se defina output_file)
        if desc_file is not None and desc_file.get('output_file') is not None:
            # Obtener la carpeta de destino
            output_path = desc_file.get('output_file').get('path', os.path.dirname(output_filename))
            # Si lo que se obtiene no es un path absoluto, anteponer la carpeta con los descriptores
            if not os.path.isabs(output_path):
                output_path = os.path.join(ConfigFile.Instance().get('folders').get('descriptor_files'), output_path)
            # Obtener el nombre del archivo de destino (sin carpeta, solo el nombre del archivo)
            output_file = desc_file.get('output_file').get('name', os.path.basename(output_filename))
            # Definir el path absoluto para el archivo de destino
            output_filename = os.path.join(output_path, output_file)
        # Retornar el nombre definido
        return output_filename

    def output_file_must_be_created(self, desc_file: dict = None) -> bool:
        # Leer configuración del script
        config = ConfigFile.Instance()
        # Si el archivo de salida no existe, debe ser creado
        if not os.path.exists(self.define_output_filename(desc_file)):
            return True
        # Si la configuración del script indica que todos los archivos de salida deben ser creados, debe ser creado
        if config.get('force_output_update', False) is True:
            return True
        # Si el descriptor indica que el archivo de salida debe ser creado, deber ser creado
        if desc_file.get('update_output', False) is True:
            return True
        # En cualquier otro caso, el archivo de salida no debe ser creado
        return False

    def read_file(self, desc_file: dict = None) -> Dataset:
        # Definir nombre del archivo a leer
        input_filename = self.define_input_filename(desc_file)
        # Retornar el ds con los datos leídos del archivo
        return self._read_strategy.read_data(input_filename, desc_file)

    def convert_file_to_netcdf(self, desc_file: dict = None) -> None:
        # Convertir archivo solo si el archivo de salida debe ser creado
        if self.output_file_must_be_created(desc_file):
            # Leer el archivo en un Dataset
            with self.read_file(desc_file) as ds:
                # Guardar el dataset en un NetCDF
                ds.to_netcdf(self.define_output_filename(desc_file))


class ReadStrategy(ABC):
    """
    The Strategy Interface (Desing Pattern -> Strategy)
    """
    @abstractmethod
    def read_data(self, file_name: str, desc_file: dict = None) -> Dataset:
        pass


class ReadCPToutputDET(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, desc_file: dict = None) -> Dataset:
        # Extraer información del archivo CPT
        info: CPToutputFileInfo = self.__extract_cpt_output_file_info(file_name)

        # Identificar el mes de corrida y los meses objetivo en el nombre del archivo
        months_regex = re.search(rf'({"|".join(Mpro.months_abbr[1:])})ic_(\d*)-?(\d*)?_', file_name)
        forecast_month, first_target_month = Mpro.month_abbr_to_int(months_regex.group(1)), int(months_regex.group(2))

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
            # OBS: init_time indica el año y mes del mes inicial (start_month, init_month, el mes con leadtime 0)
            init_year = year - 1 if forecast_month > first_target_month else year
            year_data_df.insert(2, 'init_time', pd.to_datetime(f'{init_year}-{forecast_month}-01'))
            final_df = pd.concat([final_df, year_data_df])

        # Modificar años, en caso de que sea necesario
        if desc_file is not None and desc_file.get('swap_years') is not None:

            # Obtener último año de hindcast y primer año pronosticado
            last_hindcast_year = desc_file.get('swap_years').get('last_hindcast_year')
            first_forecast_year = desc_file.get('swap_years').get('first_forecast_year')

            # OJO: El archivo que se está leyendo indica como año, el año del primer mes objetivo (y no el año de
            # inicialización del pronóstico). Sin embargo, el NetCDF generado debe indicar el año de inicialización
            # en la variable init_time (y no el año del primer mes objetivo).
            # Por lo tanto, algunas veces es necesario recalcular last_hindcast_year y first_forecast_year.
            # Esto ocurre por ejemplo para los pronósticos inicializados en diciembre y que tienen como primer mes
            # objetivo a enero (en estos tanto last_hindcast_year como first_forecast_year están un año por delante).
            last_hindcast_year = last_hindcast_year - (1 if forecast_month > first_target_month else 0)
            first_forecast_year = first_forecast_year - (1 if forecast_month > first_target_month else 0)

            # Solamente es necesario renombrar los años cuando el primer año de pronóstico (first_forecast_year)
            # es al menos dos años posterior al último año de hindcast (last_hindcast_year).
            if first_forecast_year - last_hindcast_year >= 2:

                # Identificar los años posteriores al último año de hindcast, todos estos años deben ser renombrados
                years_to_swap = set([y for y in final_df['init_time'].dt.year if y > last_hindcast_year])

                # Se crea un dataframe con los años renombrados
                anhos_renombrados = pd.DataFrame()

                # Recorrer los años que deben ser renombrados, "y" es el año a ser modificado y "n" es la
                # cantidad que debe sumarse al primer año pronosticado para obtener el año final.
                for n, y in enumerate(years_to_swap):
                    # Se hace una copia profunda del año a renombrar
                    aux = final_df.loc[final_df['init_time'].dt.year == y].copy(deep=True)
                    # Se actualiza el año en el dataframe auxiliar (que contiene un solo año)
                    aux['init_time'] = aux['init_time'].apply(lambda x: x.replace(year=first_forecast_year+n))
                    # Se agrega el dataframe aux al df con los años renombrados
                    anhos_renombrados = pd.concat([anhos_renombrados, aux])
                    # Se asgina NA al año que ya fue renombrado
                    final_df.loc[final_df['init_time'].dt.year == y, file_variable] = np.nan

                # Se reemplaza los valores con NA en final_df con los valores corregidos
                final_df = final_df.merge(anhos_renombrados, how='outer')

        # Reindexar el dataframe
        final_df = final_df.set_index(['init_time', 'latitude', 'longitude']).sort_index()

        # Transformar dataframe a dataset
        final_ds = final_df.to_xarray()

        # Agregar atributos que describan la variable
        unidad_de_medida = 'mm' if file_variable == 'prcp' else 'Celsius' if file_variable == 't2m' else None
        final_ds[file_variable].attrs['units'] = f'{unidad_de_medida}'

        # Filtrar años, en caso de que sea necesario
        if desc_file is not None and desc_file.get('filter_years') is not None:
            min_year = desc_file.get('filter_years').get('min_year')
            if min_year is not None:
                min_year = min_year - (1 if forecast_month > first_target_month else 0)
                final_ds = final_ds.where(final_ds.init_time.dt.year >= min_year, drop=True)
            max_year = desc_file.get('filter_years').get('max_year')
            if max_year is not None:
                max_year = max_year - (1 if forecast_month > first_target_month else 0)
                final_ds = final_ds.where(final_ds.init_time.dt.year <= max_year, drop=True)

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
    def read_data(self, file_name: str, desc_file: dict = None) -> Dataset:
        # Extraer información del archivo CPT
        info: CPToutputFileInfo = self.__extract_cpt_output_file_info(file_name)

        # Identificar el mes de corrida y los meses objetivo en el nombre del archivo
        months_regex = re.search(rf'({"|".join(Mpro.months_abbr[1:])})ic_(\d*)-?(\d*)?_', file_name)
        forecast_month, first_target_month = Mpro.month_abbr_to_int(months_regex.group(1)), int(months_regex.group(2))

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
                # OBS: init_time indica el año y mes del mes inicial (start_month, init_month, el mes con leadtime 0)
                init_year = year - 1 if forecast_month > first_target_month else year
                year_data_df.insert(2, 'init_time', pd.to_datetime(f'{init_year}-{forecast_month}-01'))
                year_data_df.insert(3, 'category', category)
                category_df = pd.concat([category_df, year_data_df])
            final_df = pd.concat([final_df, category_df])

        # Modificar años, en caso de que sea necesario
        if desc_file is not None and desc_file.get('swap_years') is not None:

            # Obtener último año de hindcast y primer año pronosticado
            last_hindcast_year = desc_file.get('swap_years').get('last_hindcast_year')
            first_forecast_year = desc_file.get('swap_years').get('first_forecast_year')

            # OJO: El archivo que se está leyendo indica como año, el año del primer mes objetivo (y no el año de
            # inicialización del pronóstico). Sin embargo, el NetCDF generado debe indicar el año de inicialización
            # en la variable init_time (y no el año del primer mes objetivo).
            # Por lo tanto, algunas veces es necesario recalcular last_hindcast_year y first_forecast_year.
            # Esto ocurre por ejemplo para los pronósticos inicializados en diciembre y que tienen como primer mes
            # objetivo a enero (en estos tanto last_hindcast_year como first_forecast_year están un año por delante).
            last_hindcast_year = last_hindcast_year - (1 if forecast_month > first_target_month else 0)
            first_forecast_year = first_forecast_year - (1 if forecast_month > first_target_month else 0)

            # Solamente es necesario renombrar los años cuando el primer año de pronóstico (first_forecast_year)
            # es al menos dos años posterior al último año de hindcast (last_hindcast_year).
            if first_forecast_year - last_hindcast_year >= 2:

                # Identificar los años posteriores al último año de hindcast, todos estos años deben ser renombrados
                years_to_swap = set([y for y in final_df['init_time'].dt.year if y > last_hindcast_year])

                # Se crea un dataframe con los años renombrados
                anhos_renombrados = pd.DataFrame()

                # Recorrer los años que deben ser renombrados, "y" es el año a ser modificado y "n" es la
                # cantidad que debe sumarse al primer año pronosticado para obtener el año final.
                for n, y in enumerate(years_to_swap):
                    # Se hace una copia profunda del año a renombrar
                    aux = final_df.loc[final_df['init_time'].dt.year == y].copy(deep=True)
                    # Se actualiza el año en el dataframe auxiliar (que contiene un solo año)
                    aux['init_time'] = aux['init_time'].apply(lambda x: x.replace(year=first_forecast_year+n))
                    # Se agrega el dataframe aux al df con los años renombrados
                    anhos_renombrados = pd.concat([anhos_renombrados, aux])
                    # Se asgina NA al año que ya fue renombrado
                    final_df.loc[final_df['init_time'].dt.year == y, file_variable] = np.nan

                # Se reemplaza los valores con NA en final_df con los valores corregidos
                final_df = final_df.merge(anhos_renombrados, how='outer')

        # Definir la categoría como una categoría, entonces el ordenar toma el orden
        # declarado en lugar de ordenar la categoría por orden alfabético.
        final_df['category'] = final_df['category'].astype('category')
        final_df['category'] = final_df['category'].cat.set_categories(['below', 'normal', 'above'])
        # Reindexar el dataframe
        final_df = final_df.set_index(['init_time', 'latitude', 'longitude', 'category']).sort_index()

        # La salida probabilística del CPT tiene probabilidades que van de 0 a 100
        final_df[file_variable] = final_df[file_variable] / 100

        # Transformar dataframe a dataset
        final_ds = final_df.to_xarray()

        # Agregar atributos que describan la variable
        final_ds[file_variable].attrs['units'] = '%'

        # Filtrar años, en caso de que sea necesario
        if desc_file is not None and desc_file.get('filter_years') is not None:
            min_year = desc_file.get('filter_years').get('min_year')
            if min_year is not None:
                min_year = min_year - (1 if forecast_month > first_target_month else 0)
                final_ds = final_ds.where(final_ds.init_time.dt.year >= min_year, drop=True)
            max_year = desc_file.get('filter_years').get('max_year')
            if max_year is not None:
                max_year = max_year - (1 if forecast_month > first_target_month else 0)
                final_ds = final_ds.where(final_ds.init_time.dt.year <= max_year, drop=True)

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
    def read_data(self, file_name: str, desc_file: dict = None) -> Dataset:
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
            year_data_df.insert(2, 'init_time', pd.to_datetime(f'{year}-{first_month}-01'))
            final_df = pd.concat([final_df, year_data_df])

        # Reindexar el dataframe
        final_df = final_df.set_index(['init_time', 'latitude', 'longitude']).sort_index()

        # Transformar dataframe a dataset
        final_ds = final_df.to_xarray()

        # Agregar atributos que describan la variable
        unidad_de_medida = 'mm' if file_variable == 'prcp' else 'Celsius' if file_variable == 't2m' else None
        final_ds[file_variable].attrs['units'] = f'{unidad_de_medida}'

        # Filtrar años, en caso de que sea necesario
        if desc_file is not None and desc_file.get('filter_years') is not None:
            min_year = desc_file.get('filter_years').get('min_year')
            if min_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year >= min_year, drop=True)
            max_year = desc_file.get('filter_years').get('max_year')
            if max_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year <= max_year, drop=True)

        # Return generated dataset
        return final_ds


class ReadCPTpredictor(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, desc_file: dict = None) -> Dataset:
        # Extraer información del archivo CPT
        df_info: List[CPTpredictorFileInfo] = self.__extract_cpt_predictor_file_info(file_name)

        # Identificar la variable en el nombre del archivo
        print(file_name)
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
            df.insert(0, 'init_time', info.start_date)
            final_df = pd.concat([final_df, df])

        # Reindexar el dataframe
        final_df = final_df.set_index(['init_time', 'latitude', 'longitude']).sort_index()

        # Transformar dataframe a dataset
        final_ds = final_df.to_xarray()

        # Agregar atributos que describan la variable
        unidad_de_medida = 'mm' if file_variable == 'prcp' else 'Celsius' if file_variable == 't2m' else None
        final_ds[file_variable].attrs['units'] = f'{unidad_de_medida}'

        # Filtrar años, en caso de que sea necesario
        if desc_file is not None and desc_file.get('filter_years') is not None:
            min_year = desc_file.get('filter_years').get('min_year')
            if min_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year >= min_year, drop=True)
            max_year = desc_file.get('filter_years').get('max_year')
            if max_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year <= max_year, drop=True)

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
    def read_data(self, file_name: str, desc_file: dict = None) -> Dataset:
        # Identificar el mes de corrida en el nombre del archivo
        forecast_month = re.search(rf'({"|".join(Mpro.months_abbr[1:])})', file_name).group(0)
        forecast_month = Mpro.month_abbr_to_int(forecast_month)

        # Identificar la variable en el nombre del archivo
        file_variable = re.search(r'(prec|tref)', file_name).group(0)
        file_variable = 'prcp' if file_variable == 'prec' else 't2m' if file_variable == 'tref' else None

        # Identificar trimestre objetivo
        season_months = re.search(rf'({"|".join(Mpro.trimesters[1:])})', file_name).group(0)

        # Extraer de la configuración el primer año en el archivo
        first_year = desc_file.get('first_year_in_file', DEFAULT_START_YEAR) \
            if desc_file is not None else DEFAULT_START_YEAR

        # Determinar si el archivo es de tipo hindcast o no
        is_hindcast = ('_hind.npz' in file_name)

        # Leer archivo de tipo npz
        with np.load(file_name) as npz:
            # Identificar variable con datos
            data_variable = [x for x in npz.files if x not in ['lat', 'lon']][0]
            # Los archivos de tipo hindcast y real_time tiene diferentes estructuras. Por lo tanto se los lee de manera
            # diferente. Los hindcasts tienen datos para muchos años, los real_time tienen un solo año.
            if is_hindcast:
                # Identificar la cantidad de años en el archivo
                n_years = len(npz[data_variable])
                # Crear dataset con los datos
                final_ds = xr.Dataset(
                    data_vars={
                        file_variable: (['init_time', 'latitude', 'longitude'], np.squeeze(npz[data_variable][:, :, :]))
                    },
                    coords={
                        # "init_time" debe ser la fecha de inicio de la corrida, es decir, para un prono corrido en
                        #      diciembre de 2020 para enero de 2021, init_time debe tener como año al 2020, no el 2021.
                        #      CPT retorna como año en los archivos de salida, el año del primer mes objetivo, es decir,
                        #      2021 en el ejemplo anterior, por lo que, en el caso del CPT, el año en los archivos de
                        #      salida no pueden usarse sin pre-procesarlos.
                        # OBS: como el archivo de salida no tiene años y siempre se asigna el primer año del hindcast
                        #      al primer año en el archivo, entonces se asume que este año es siempre el año de inicio
                        #      de la corrida y no el año del primer mes objetivo del pronóstico. Por lo tanto, a
                        #      diferencia de lo que pasa con los archivos de salida del CPT, aquí sí se puede usar
                        #      directamente el año.
                        'init_time': pd.date_range(f"{first_year}-{forecast_month}-01", periods=n_years, freq='12MS'),
                        'latitude': npz['lat'],
                        'longitude': npz['lon']
                    })
            else:
                # Crear dataset con los datos
                final_ds = xr.Dataset(
                    data_vars={
                        file_variable: (['latitude', 'longitude'], np.squeeze(npz[data_variable][:, :]))
                    },
                    coords={
                        'latitude': npz['lat'],
                        'longitude': npz['lon']
                    })
                # Identificar el año de pronósticos real_time
                forecast_year = re.search(rf'(?:{"|".join(Mpro.months_abbr[1:])})(\d{{4}})', file_name).group(1)
                # Agregar init_time al dataset
                # "init_time" debe ser la fecha de inicio de la corrida, es decir, para un prono corrido en diciembre
                #      de 2020 para enero de 2021, init_time debe tener como año al 2020, no el 2021. CPT retorna como
                #      año en los archivos de salida, el año del primer mes objetivo, es decir, 2021 en el ejemplo
                #      anterior, por lo que, en el caso del CPT, el año en los archivos de salida no pueden usarse
                #      sin pre-procesarlos.
                final_ds = final_ds.expand_dims(
                    init_time=pd.date_range(f"{forecast_year}-{forecast_month}-01", periods=1)).copy(deep=True)

        # Corregir valor total pronosticado (se debe multiplicar por la cantidad de días del mes o del trimestre)
        for year in final_ds.init_time.dt.year:
            n_days = Mpro.n_days_in_trimester(season_months, calendar.isleap(int(year.values)))
            final_ds.loc[{'init_time': str(year.values)}] = final_ds.sel(init_time=str(year.values)) * n_days

        # Agregar atributos que describan la variable
        unidad_de_medida = 'mm' if file_variable == 'prcp' else 'Celsius' if file_variable == 't2m' else None
        final_ds[file_variable].attrs['units'] = f'{unidad_de_medida} anomaly'

        # Filtrar años, en caso de que sea necesario
        if desc_file is not None and desc_file.get('filter_years') is not None:
            min_year = desc_file.get('filter_years').get('min_year')
            if min_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year >= min_year, drop=True)
            max_year = desc_file.get('filter_years').get('max_year')
            if max_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year <= max_year, drop=True)

        # Return generated dataset
        return final_ds


class ReadEREGoutputPROB(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, desc_file: dict = None) -> Dataset:
        # Identificar el mes de corrida en el nombre del archivo
        forecast_month = re.search(rf'({"|".join(Mpro.months_abbr[1:])})', file_name).group(0)
        forecast_month = Mpro.month_abbr_to_int(forecast_month)

        # Identificar la variable en el nombre del archivo
        file_variable = re.search(r'(prec|tref)', file_name).group(0)
        file_variable = 'prcp' if file_variable == 'prec' else 't2m' if file_variable == 'tref' else None

        # Extraer de la configuración el primer año en el archivo
        first_year = desc_file.get('first_year_in_file', DEFAULT_START_YEAR) \
            if desc_file is not None else DEFAULT_START_YEAR

        # Determinar si el archivo es de tipo hindcast o no
        is_hindcast = ('_hind.npz' in file_name)

        # Leer archivo de tipo npz
        with np.load(file_name) as npz:
            # Identificar variable con datos
            data_variable = [x for x in npz.files if x not in ['lat', 'lon']][0]

            # Los archivos de tipo hindcast y real_time tiene diferentes estructuras. Por lo tanto se los lee de manera
            # diferente. Los hindcasts tienen datos para muchos años, los real_time tienen un solo año.
            if is_hindcast:

                # Identificar la cantidad de años en el archivo
                n_years = len(npz[data_variable][0])

                # Nombre de dimensiones: ['category', 'init_time', 'latitude', 'longitude']
                for_terciles = np.squeeze(npz[data_variable][:, :, :, :])

                # Se extraen las probabilidades en el archivo npz
                below = for_terciles[0, :, :, :]
                near_as = for_terciles[1, :, :, :]  # normal + below
                # Se calcula la probabilidad de un evento superior a la media
                above = 1 - near_as
                normal = near_as - below

                # Se crea la matriz con la que se creará el dataset
                for_terciles = np.concatenate([below[:, :, :, np.newaxis], normal[:, :, :, np.newaxis],
                                               above[:, :, :, np.newaxis]], axis=3)

                # Crear dataset con los datos
                final_ds = xr.Dataset(
                    data_vars={
                        file_variable: (['init_time', 'latitude', 'longitude', 'category'], for_terciles)
                    },
                    coords={
                        # Time debe ser la fecha de inicio de la corrida, es decir, para un prono corrido en diciembre
                        #      de 2020 para enero de 2021, init_time debe tener como año al 2020, no el 2021. CPT
                        #      retorna como año en los archivos de salida, el año del primer mes objetivo, es decir,
                        #      2021 en el ejemplo anterior, por lo que, en el caso del CPT, el año en los archivos de
                        #      salida no pueden usarse sin pre-procesarlos.
                        # OBS: como el archivo de salida no tiene años y siempre se asigna el primer año del hindcast
                        #      al primer año en el archivo, entonces se asume que este año es siempre el año de inicio
                        #      de la corrida y no el año del primer mes objetivo del pronóstico. Por lo tanto, a
                        #      diferencia de lo que pasa con los archivos de salida del CPT, aquí sí se puede usar
                        #      directamente el año.
                        'init_time': pd.date_range(f"{first_year}-{forecast_month}-01", periods=n_years, freq='12MS'),
                        'latitude': npz['lat'],
                        'longitude': npz['lon'],
                        'category': ['below', 'normal', 'above']
                    })

            else:

                # Nombre de dimensiones: ['category', 'latitude', 'longitude']
                for_terciles = np.squeeze(npz[data_variable][:, :, :])

                # Se extraen las probabilidades en el archivo npz
                below = for_terciles[0, :, :]
                near_as = for_terciles[1, :, :]  # normal + below
                # Se calcula la probabilidad de un evento superior a la media
                above = 1 - near_as
                normal = near_as - below

                # Se crea la matriz con la que se creará el dataset
                for_terciles = np.concatenate([below[:, :, np.newaxis], normal[:, :, np.newaxis],
                                               above[:, :, np.newaxis]], axis=2)

                # Crear dataset con los datos
                final_ds = xr.Dataset(
                    data_vars={
                        file_variable: (['latitude', 'longitude', 'category'], for_terciles)
                    },
                    coords={
                        'latitude': npz['lat'],
                        'longitude': npz['lon'],
                        'category': ['below', 'normal', 'above']
                    })
                # Identificar el año de pronósticos real_time
                forecast_year = re.search(rf'(?:{"|".join(Mpro.months_abbr[1:])})(\d{{4}})', file_name).group(1)
                # Agregar init_time al dataset
                # "init_time" debe ser la fecha de inicio de la corrida, es decir, para un prono corrido en diciembre
                #      de 2020 para enero de 2021, init_time debe tener como año al 2020, no el 2021. CPT retorna como
                #      año en los archivos de salida, el año del primer mes objetivo, es decir, 2021 en el ejemplo
                #      anterior, por lo que, en el caso del CPT, el año en los archivos de salida no pueden usarse
                #      sin pre-procesarlos.
                final_ds = final_ds.expand_dims(
                    init_time=pd.date_range(f"{forecast_year}-{forecast_month}-01", periods=1)).copy(deep=True)

        # Agregar atributos que describan la variable
        final_ds[file_variable].attrs['units'] = '%'

        # Filtrar años, en caso de que sea necesario
        if desc_file is not None and desc_file.get('filter_years') is not None:
            min_year = desc_file.get('filter_years').get('min_year')
            if min_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year >= min_year, drop=True)
            max_year = desc_file.get('filter_years').get('max_year')
            if max_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year <= max_year, drop=True)

        # Return generated dataset
        return final_ds


class ReadEREGobservedData(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, desc_file: dict = None) -> Dataset:
        # Identificar la variable en el nombre del archivo
        file_variable = re.search(r'(prec|tref)', file_name).group(0)
        file_variable = 'prcp' if file_variable == 'prec' else 't2m' if file_variable == 'tref' else None

        # Identificar trimestre objetivo
        season_months = re.search(rf'({"|".join(Mpro.trimesters[1:])})', file_name).group(0)
        first_month = Mpro.first_month_of_trimester(season_months)

        # Extraer de la configuración el primer año en el archivo
        first_year = int(re.search(r'_(\d{4})_', file_name).group(1))

        # Leer archivo de tipo npz
        with np.load(file_name) as npz:
            # Identificar variable con datos
            # OBS: este archivo .npz tiene el valor determinístico -que se guarda en el netcdf-, el tercil al cual
            # corresponde ese valor y la categoría -ni el tercil ni la categoría se guardan en el netcdf final-.
            data_variable = [x for x in npz.files if x not in ['lats_obs', 'lons_obs']]

            # Identificar la cantidad de años en el archivo
            n_years = len(npz['obs_dt'])

            # Crear dataset con los datos
            final_ds = xr.Dataset(
                data_vars={
                    file_variable: (['init_time', 'latitude', 'longitude'], np.squeeze(npz['obs_dt'][:, :, :]))
                },
                coords={
                    'init_time': pd.date_range(f"{first_year}-{first_month}-01", periods=n_years, freq='12MS'),
                    'latitude': npz['lats_obs'],
                    'longitude': npz['lons_obs']
                })

        # Corregir valor total pronosticado (se debe multiplicar por la cantidad de días del mes o del trimestre)
        for year in final_ds.init_time.dt.year:
            n_days = Mpro.n_days_in_trimester(season_months, calendar.isleap(int(year.values)))
            final_ds.loc[{'init_time': str(year.values)}] = final_ds.sel(init_time=str(year.values)) * n_days

        # Agregar atributos que describan la variable
        unidad_de_medida = 'mm' if file_variable == 'prcp' else 'Celsius' if file_variable == 't2m' else None
        final_ds[file_variable].attrs['units'] = f'{unidad_de_medida} anomaly'

        # Filtrar años, en caso de que sea necesario
        if desc_file is not None and desc_file.get('filter_years') is not None:
            min_year = desc_file.get('filter_years').get('min_year')
            if min_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year >= min_year, drop=True)
            max_year = desc_file.get('filter_years').get('max_year')
            if max_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year <= max_year, drop=True)

        # Return generated dataset
        return final_ds


class ReadCRCSASobs(ReadStrategy):
    """
    A Concrete Strategy (Desing Pattern -> Strategy)
    """
    def read_data(self, file_name: str, desc_file: dict = None) -> Dataset:

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

        # Filtrar años, en caso de que sea necesario
        if desc_file is not None and desc_file.get('filter_years') is not None:
            min_year = desc_file.get('filter_years').get('min_year')
            if min_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year >= min_year, drop=True)
            max_year = desc_file.get('filter_years').get('max_year')
            if max_year is not None:
                final_ds = final_ds.where(final_ds.init_time.dt.year <= max_year, drop=True)

        # Return generated dataset
        return final_ds

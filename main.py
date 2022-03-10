#!/usr/bin/env python

from errors import DescriptorError
from configuration import ConfigFile, DescriptorFile
from read_strategies import FileReader
from read_strategies import ReadEREGoutputDET, ReadEREGoutputPROB, \
    ReadCPToutputDET, ReadCPToutputPROB, ReadCPTpredictand, ReadCPTpredictor, \
    ReadCRCSASobs

import os


def define_read_strategy(file_type: str, descriptor_filename: str):
    if file_type == 'ereg_det_output':
        return ReadEREGoutputDET()
    elif file_type == 'ereg_prob_output':
        return ReadEREGoutputPROB()
    elif file_type == 'crcsas_obs_data':
        return ReadCRCSASobs()
    elif file_type == 'cpt_det_output':
        return ReadCPToutputDET()
    elif file_type == 'cpt_prob_output':
        return ReadCPToutputPROB()
    elif file_type == 'cpt_predictand':
        return ReadCPTpredictand()
    elif file_type == 'cpt_predictor':
        return ReadCPTpredictor()
    else:
        raise DescriptorError(f'El tipo de archivo indicado "{file_type}" es incorrecto. '
                              f'Verifique el descriptor: {descriptor_filename}.')


if __name__ == '__main__':

    config = ConfigFile.Instance()
    desc_files_folder = config.get('folders').get('descriptor_files')

    # Obtener listado de archivos de configuración
    desc_files = sorted(os.listdir(desc_files_folder))
    desc_files = [f for f in desc_files if f.endswith('.yaml') and f != 'template.yaml']

    # Procesar cada uno de los archivos de configuración
    for dn, df in enumerate(desc_files):

        # Leer el archivo de configuración
        descriptor = DescriptorFile(f'{desc_files_folder}/{df}')

        # Obtener listado de archivos a transformar
        proc_files = descriptor.get('files')

        # Descartar archivos que no deben ser creados
        proc_files = [f for f in proc_files if FileReader.output_file_must_be_created(f)]

        # Si no hay archivos por procesar, continuar con el siguiente descriptor
        if len(proc_files) == 0:
            continue

        # Convertir los archivos indicados en el archivo de configuración
        for pn, pf in enumerate(proc_files):

            # Definir estrategia de lectura del archivo
            read_strategy = define_read_strategy(pf.get('type'), df)

            # Definir el objeto encargado de leer y convertir el archivo
            reader = FileReader(read_strategy)

            # Convertir archivo a NetCDF
            reader.convert_file_to_netcdf(desc_file=pf)

            # Informar avance
            print(f'\r F: {pn+1}/{len(proc_files)} -- ({df})', end='')

        # Suprimir retorno de carro
        print('')

    if len(desc_files) == 0:
        print(' F: 0/0 -- ()')

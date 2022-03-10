#!/usr/bin/env python

import os
import logging

# Change current directory
if os.path.dirname(__file__):
    os.chdir(os.path.dirname(__file__))

from errors import DescriptorError
from configuration import ConfigFile, DescriptorFile
from read_strategies import FileReader
from read_strategies import ReadEREGoutputDET, ReadEREGoutputPROB
from read_strategies import ReadCPToutputDET, ReadCPToutputPROB, ReadCPTpredictand, ReadCPTpredictor
from read_strategies import ReadCRCSASobs


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
    # Conf logging
    logging.basicConfig(format='%(asctime)s -- %(message)s', datefmt='%Y/%m/%d %I:%M:%S %p', level=logging.INFO)

    # Reportar inicio de la ejecución
    logging.info('')
    logging.info('THE START')

    # Read processor config file
    config = ConfigFile.Instance()
    desc_files_folder = config.get('folders').get('descriptor_files')

    # Obtener listado de archivos de configuración
    desc_files = sorted(os.listdir(desc_files_folder))
    desc_files = [f for f in desc_files if f.endswith('.yaml') and f != 'template.yaml']

    # Procesar cada uno de los archivos de configuración
    files_count = 0
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

        # Agregar una línea para separar la salida del log
        logging.info('')

        # Convertir los archivos indicados en el archivo de configuración
        for pn, pf in enumerate(proc_files):

            # Definir estrategia de lectura del archivo
            read_strategy = define_read_strategy(pf.get('type'), df)

            # Definir el objeto encargado de leer y convertir el archivo
            reader = FileReader(read_strategy)

            # Convertir archivo a NetCDF
            reader.convert_file_to_netcdf(desc_file=pf)

            # Informar avance
            logging.info(f'Processed files: {pn+1}/{len(proc_files)} -- ({df})')

            # Contar archivo
            files_count += 1

    # En caso de que no se haya procesado ningún archivo, se informa lo siguiente
    if len(desc_files) == 0 or files_count == 0:
        logging.info('')
        logging.info('Processed files: 0/0 -- ()')

    # Reportar final de la ejecución
    logging.info('')
    logging.info('THE END')
    logging.info('')

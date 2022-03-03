#!/usr/bin/env python

from configuration import ConfigFile, ConfigError
from read_strategies import FileReader
from read_strategies import ReadEREGoutputDET, ReadEREGoutputPROB, \
    ReadCPToutputDET, ReadCPToutputPROB, ReadCPTpredictand, ReadCPTpredictor, \
    ReadCRCSASobs

import os.path
import argparse
import shutil


def parse_arguments():
    # Definir argumentos
    parser = argparse.ArgumentParser(description='Files processor')
    #
    parser.add_argument('-f', '--config_folder', type=str, nargs=1, default='config_files',
                        help='folder that contains the configuration files to be processed.')
    parser.add_argument('-a', '--archive_folder', type=str, nargs=1, default='config_files_archive',
                        help='folder that contains the configuration files already processed.')

    # Retornan argumentos parseados
    return parser.parse_args()


def archive_config_file(config_file, src_folder, dst_folder):
    # Contar cuantos archivos con el mismo nombre hay en la carpeta destino
    n_dst_files = sum(1 for dst_f in os.listdir(args.archive_folder) if dst_f == config_file)

    # Definir el nombre final del archivo
    final_config_file = config_file

    # Modificar el nombre del archivo en caso de que sea necesario
    if n_dst_files:
        final_config_file = f"{os.path.splitext(config_file)[0]}_{str(n_dst_files + 1)}.yaml"

    # Mover el archivo
    shutil.move(f'{src_folder}/{config_file}', f'{dst_folder}/{final_config_file}')


def define_read_strategy(file_type):
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
        raise ConfigError('El tipo de archivo indicado es incorrecto')


if __name__ == '__main__':

    # Parsear argumentos
    args = parse_arguments()

    # Obtener listado de archivos de configuración
    config_files = sorted(os.listdir(args.config_folder))
    config_files = [f for f in config_files if f.endswith('.yaml')]
    config_files = [f for f in config_files if "template" not in f]

    # Procesar cada uno de los archivos de configuración
    for nn, cf in enumerate(config_files):

        # Leer el archivo de configuración
        config = ConfigFile(config_file=f'{args.config_folder}/{cf}')

        # Obtener listado de archivos a transformar
        files = config.get('files')

        # Convertir los archivos indicados en el archivo de configuración
        for n, f in enumerate(files):

            # Definir estrategia de lectura del archivo
            read_strategy = define_read_strategy(f.get('type'))

            # Definir el objeto encargado de leer y convertir el archivo
            reader = FileReader(read_strategy)

            # Definir nombre del archivo a leer
            file_name = os.path.join(f.get('path'), f.get('name'))

            # Convertir archivo a NetCDF
            reader.convert_file_to_netcdf(file_name, file_config=f)

            # Informar avance
            print(f'\r CF: {nn+1}/{len(config_files)} -- F: {n+1}/{len(files)} -- ({cf})', end='')

        # Mover el archivo de configuración procesado al archivo
        archive_config_file(cf, args.config_folder, args.archive_folder)

        # Suprimir retorno de carro
        print('')

    if len(config_files) == 0:
        print(' CF: 0/0 -- F: 0/0')

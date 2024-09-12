#!/usr/bin/env python

import os
import logging

# Change current directory
if os.path.dirname(__file__):
    os.chdir(os.path.dirname(__file__))

from pathlib import Path

from script import ScriptControl
from errors import DescriptorError
from configuration import ConfigFile, DescriptorFile
from read_strategies import FileReader
from read_strategies import ReadEREGoutputDET, ReadEREGoutputPROB, ReadEREGoutputSISSA, ReadEREGobservedData
from read_strategies import ReadCPToutputDET, ReadCPToutputPROB, ReadCPTpredictand, ReadCPTpredictor
from read_strategies import ReadCRCSASobs


def define_read_strategy(file_type: str, descriptor_filename: str):
    if file_type == 'ereg_det_output':
        return ReadEREGoutputDET()
    elif file_type == 'ereg_prob_output':
        return ReadEREGoutputPROB()
    elif file_type == 'ereg_sissa_output':
        return ReadEREGoutputSISSA()
    elif file_type == 'ereg_obs_data':
        return ReadEREGobservedData()
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

    # Create script control
    script = ScriptControl('files-processor')

    # Start script execution
    script.start_script()

    # Read processor config file
    config = ConfigFile.Instance()
    desc_files_folder = config.get('folders').get('descriptor_files')

    # Obtener listado de archivos de configuración
    desc_files = sorted(Path(desc_files_folder).rglob("*.yaml"))
    desc_files = [f for f in desc_files if f.name != 'template.yaml']

    # Procesar cada uno de los archivos de configuración
    files_count = 0
    missing_files_count = 0
    processed_files_count = 0
    for dn, df in enumerate(desc_files):

        # Leer el archivo de configuración
        descriptor = DescriptorFile(df.absolute().as_posix())

        # Obtener listado de archivos a transformar
        proc_files = descriptor.get('files')

        # Convertir los archivos indicados en el archivo de configuración
        for pn, pf in enumerate(proc_files):

            # Contar archivo
            files_count += 1

            # Definir estrategia de lectura del archivo
            read_strategy = define_read_strategy(pf.get('type'), df.absolute().as_posix())

            # Definir el objeto encargado de leer y convertir el archivo
            reader = FileReader(read_strategy, df)

            # Si el archivo no existe, reportar el problema y continuar
            input_file = reader.define_input_filename(pf)
            if not os.path.isfile(input_file):
                missing_files_count += 1
                logging.warning(f"Missing file: {input_file}")
                continue

            # Si el archivo ya existe y no debe ser sobrescrito, no se deben ejecutar las líneas a continuación
            if not reader.output_file_must_be_created(pf):
                continue

            # Convertir archivo a NetCDF
            reader.convert_file_to_netcdf(desc_file=pf)

            # Contar archivos procesados
            processed_files_count += 1

            # Informar avance
            logging.info(f'Processed files: {pn+1}/{len(proc_files)} -- ({df.absolute().as_posix()})')

    # En caso de que no se haya procesado ningún archivo, se informa lo siguiente
    if len(desc_files) == 0 or files_count == 0:
        logging.info('')
        logging.info('Processed files: 0/0')

    # Reportar la cantida de archivos procesados
    if files_count > 0:
        logging.info('')
        logging.info(f'Processed files: {processed_files_count}/{files_count}')

    # Reportar la cantidad de archivos perdidos
    if missing_files_count > 0:
        logging.info('')
        logging.warning(f'Missing files: {missing_files_count}/{files_count}')

    # End script execution
    script.end_script_execution()

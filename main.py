import os.path

from configuration import ConfigFile, ConfigError
from read_strategies import FileReader
from read_strategies import ReadEregDEToutput, ReadEregPROBoutput, ReadCRCSASobs, \
    ReadCPToutput, ReadCPTpredictand, ReadCPTpredictor

if __name__ == '__main__':

    # Leer el archivo de configuración
    config = ConfigFile.Instance()

    # Convertir los archivos indicados en el archivo de configuración
    for f in config.get('files'):

        # Definir la estrategia de lectura del archivo
        read_strategy = None
        if f.get('type') == 'ereg_det_output':
            read_strategy = ReadEregDEToutput()
        elif f.get('type') == 'ereg_prob_output':
            read_strategy = ReadEregPROBoutput()
        elif f.get('type') == 'crcsas_obs_data':
            read_strategy = ReadCRCSASobs()
        elif f.get('type') == 'cpt_output':
            read_strategy = ReadCPToutput()
        elif f.get('type') == 'cpt_predictand':
            read_strategy = ReadCPTpredictand()
        elif f.get('type') == 'cpt_predictor':
            read_strategy = ReadCPTpredictor()
        else:
            raise ConfigError('El tipo de archivo indicado es incorrecto')

        # Definir el objeto encargado de leer y convertir el archivo
        reader = FileReader(read_strategy)

        if f.get('name') == 'nmme_precip-prcp_chirps_Janic_2_1991-2020_2022_1.txt':
            stop = True

        # Convertir archivo a NetCDF
        reader.convert_file_to_netcdf(os.path.join(f.get('path'), f.get('name')))



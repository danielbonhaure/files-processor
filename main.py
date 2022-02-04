import os.path

from configuration import ConfigFile, ConfigError
from read_strategies import FileReader
from read_strategies import ReadEREGoutputDET, ReadEREGoutputPROB, \
    ReadCPToutputDET, ReadCPToutputPROB, ReadCPTpredictand, ReadCPTpredictor, \
    ReadCRCSASobs

if __name__ == '__main__':

    # Leer el archivo de configuración
    config = ConfigFile.Instance()

    # Convertir los archivos indicados en el archivo de configuración
    for f in config.get('files'):

        # Definir la estrategia de lectura del archivo
        read_strategy = None
        if f.get('type') == 'ereg_det_output':
            read_strategy = ReadEREGoutputDET()
        elif f.get('type') == 'ereg_prob_output':
            read_strategy = ReadEREGoutputPROB()
        elif f.get('type') == 'crcsas_obs_data':
            read_strategy = ReadCRCSASobs()
        elif f.get('type') == 'cpt_det_output':
            read_strategy = ReadCPToutputDET()
        elif f.get('type') == 'cpt_prob_output':
            read_strategy = ReadCPToutputPROB()
        elif f.get('type') == 'cpt_predictand':
            read_strategy = ReadCPTpredictand()
        elif f.get('type') == 'cpt_predictor':
            read_strategy = ReadCPTpredictor()
        else:
            raise ConfigError('El tipo de archivo indicado es incorrecto')

        # Definir el objeto encargado de leer y convertir el archivo
        reader = FileReader(read_strategy)

        # Definir nombre del archivo a leer
        file_name = os.path.join(f.get('path'), f.get('name'))

        # Convertir archivo a NetCDF
        reader.convert_file_to_netcdf(file_name, file_config=f)




import os
import logging

from abc import ABC, abstractmethod
from pathlib import Path
from redis import Redis
from redis.exceptions import RedisError
from typing import Union

from configuration import ConfigFile


class PidDB(ABC):

    @classmethod
    @abstractmethod
    def available(cls) -> bool:
        pass

    @abstractmethod
    def set(self, script_name: str, value: Union[str, int, float]):
        pass

    @abstractmethod
    def get(self, script_name: str) -> Union[str, int, float, None]:
        pass

    @abstractmethod
    def delete(self, script_name: str):
        pass


class FileDB(PidDB):
    folder: Path = Path(os.getenv('FPROC_HOME', '/tmp'))

    @classmethod
    def available(cls) -> bool:
        return True

    def __file_path(self, file_name: str) -> Path:
        return Path(self.folder, f'{file_name}.pid')

    def set(self, script_name: str, value: Union[str, int, float]):
        file_path: Path = self.__file_path(script_name)
        with open(file_path, 'w') as f:
            f.write(f'{value}')

    def get(self, script_name: str) -> Union[str, int, float, None]:
        file_path: Path = self.__file_path(script_name)
        if file_path.is_file():
            return file_path.read_text()
        return None

    def delete(self, script_name: str):
        file_path: Path = self.__file_path(script_name)
        if file_path.is_file():
            file_path.unlink()


class RedisDB(PidDB):
    host: str = os.getenv('REDIS_HOST', 'localhost')
    port: int = int(os.getenv('REDIS_PORT', 6379))

    @staticmethod
    def __conn_is_valid(conn: Redis) -> bool:
        try:
            conn.ping()
        except RedisError:
            return False
        else:
            return True

    @classmethod
    def available(cls) -> bool:
        r = Redis(host=cls.host, port=cls.port, decode_responses=True)
        return cls.__conn_is_valid(r)

    def set(self, script_name: str, value: Union[str, int, float]):
        r = Redis(host=self.host, port=self.port, decode_responses=True)
        if self.__conn_is_valid(r):
            r.set(script_name, value)

    def get(self, script_name: str) -> Union[str, int, float, None]:
        r = Redis(host=self.host, port=self.port, decode_responses=True)
        if self.__conn_is_valid(r):
            return r.get(script_name)
        return None

    def delete(self, script_name: str):
        r = Redis(host=self.host, port=self.port, decode_responses=True)
        if self.__conn_is_valid(r):
            r.delete(script_name)


class ScriptControl(object):

    # Definir log levels válidos
    valid_log_levels = list(logging.getLevelNamesMapping())

    def __init__(self, script_name: str, single_instance: bool = True):
        # Define instance variables
        self.script_name: str = script_name
        self.pid: int = -1  # PID -1 is a temporal invalid PID
        self.pid_db: PidDB = RedisDB() if RedisDB.available() else FileDB()
        self.single_instance: bool = single_instance
        # Setup logger
        self.setup_logger()

    @property
    def log_level(self) -> str:
        # Prioridad 1: variable de entorno LOG_LEVEL
        env_log_level = os.getenv('LOG_LEVEL')
        if env_log_level and env_log_level in self.valid_log_levels:
            return env_log_level
        # Prioridad 2: archivo de configuración config.yaml
        config_log_level = ConfigFile.Instance().get('log_level')
        if config_log_level and config_log_level in self.valid_log_levels:
            return config_log_level
        # Valor por defecto: INFO
        return 'INFO'

    def setup_logger(self):
        log_level_int = logging.getLevelName(self.log_level)
        logging.basicConfig(format='%(asctime)s -- %(levelname)4s -- %(message)s',
                            datefmt='%Y/%m/%d %I:%M:%S %p', level=log_level_int)

    def start_script(self):
        # Abort if an instance is already running (when needed)
        if self.single_instance:
            self.assert_not_running()
        # Get and save PID
        self.pid = os.getpid()
        self.pid_db.set(self.script_name, self.pid)
        # Report start
        logging.info(f'Starting script {self.script_name} (w/PID: {self.pid})')

    def assert_not_running(self):
        # Verify if script is running, by getting its PID
        previously_saved_pid = self.pid_db.get(self.script_name)
        # Stop script execution if there is another instance running
        if previously_saved_pid is not None:
            logging.error(f"Script {self.script_name} was expected not to be running "
                          f"but is currently running w/PID {previously_saved_pid}")
            raise SystemExit(1)

    def end_script_execution(self):
        # Remove saved PID
        self.pid_db.delete(self.script_name)
        # Report execution end
        logging.info(f'Ending script {self.script_name} (w/PID: {self.pid})')

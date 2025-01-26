import toml
import pprint
from loguru import logger

class ConfigLoader:
    def __init__(self, config_file):
        self._config_file = config_file
        self._config = self.load_config()
        logger.info(f"Loaded config file: '{self._config_file}'")

    def load_config(self):
        try:
            return toml.load(self._config_file)
        except FileNotFoundError:
            logger.error(f"Config file '{self._config_file}' not found.")
            exit(1)
    
    def get_keys(self, key):
        return self._config.get(key)
    
    def add_key(self, key, value):
        if self._config.get(key) is None:
            logger.debug(f"No key '{key}' exists, adding value '{value}'")
            self._config[key] = value
        elif isinstance(self._config[key], dict):
            logger.debug(f"Key '{key}' exists as dict, updating value '{value}'")
            self._config[key].update(value)
        elif isinstance(self._config[key], list):
            logger.debug(f"Key '{key}' exists as list, extending value '{value}'")
            self._config[key].extend(value)
        else:
            logger.debug(f"Key '{key}' exists, changing value '{value}'")
            self._config[key] = value
        with open(self._config_file, 'w', encoding='utf-8') as f:
            toml.dump(self._config, f)

    
    def __repr__(self) -> str:
        return pprint.saferepr(self._config)

if __name__ == "__main__":
    config_loader = ConfigLoader('config.test.toml')
    logger.debug(config_loader)
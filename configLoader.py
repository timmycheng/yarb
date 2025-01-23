import toml

class ConfigLoader:
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        try:
            return toml.load(self.config_file)
        except FileNotFoundError:
            print(f"Config file '{self.config_file}' not found.")
    
    def __repr__(self) -> str:
        return f"ConfigLoader(\n" + \
               "\n".join(f"    {key}: {value}" for key, value in self.config.items()) + \
               "\n)"

if __name__ == "__main__":
    config_loader = ConfigLoader('config-new.toml')
    print(config_loader)
import os
import toml

print(__file__)
print(os.getcwd())
print(os.path.dirname(__file__))

config=toml.load('config.toml')
print(config['rss'])
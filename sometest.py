import os
import toml

print(__file__)
print(os.getcwd())
print(os.path.dirname(__file__))

config=toml.load('config.toml')
print(config)
# with toml.load('config.toml') as config:
#     print(config['rss'])

import time

from loguru import logger
from tqdm import tqdm

logger.remove()
logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)

logger.info("Initializing")

for x in tqdm(range(100)):
    logger.error("Iterating #{}", x)
    time.sleep(2)


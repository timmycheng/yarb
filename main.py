# *
import argparse
from loguru import logger
from toml import load


def loadConfig(test_flag: bool = False):
    if test_flag:
        return load("config-test.toml")
    else:
        return load("config.toml")


def update():
    pass


def getArticles():
    pass


def init():
    pass


def notify():
    pass


def cleanup():
    pass


def getArgs():
    args=argparse.ArgumentParser()
    args.add_argument("-t", "--test", action="store_true", help="Use test config file",default=False,required=False)
    args.add_argument("-r", "--rss", action="store_true", help="Update RSSs")
    args.add_argument("-b", "--bot", action="store_true", help="Test bots")
    args.add_argument("-d","--today", action="store_true", help="Update today")
    return args.parse_args()


def main():
    args=getArgs()
    conf=loadConfig(args.test)
    logger.info(f'Config loaded: {len(conf)}')
    pass


if __name__ == "__main__":
    main()

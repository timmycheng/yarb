# *
import argparse
from configloader import ConfigLoader
from loguru import logger

config={}

def update():
    print(config)
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
    global config
    args=getArgs()
    if args.test:
        config=ConfigLoader("config.test.toml")
    else:
        config=ConfigLoader("config.toml")
    config.add_key("test","test")


if __name__ == "__main__":
    main()

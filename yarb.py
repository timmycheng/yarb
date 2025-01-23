#!/usr/bin/python3

import os
import json
import sys
import time
import asyncio
import schedule
import pyfiglet
import argparse
import datetime
import listparser
import feedparser
import toml
import requests
import threading

from tqdm import tqdm
from pathlib import Path
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed

from bot import *
from utils import *

requests.packages.urllib3.disable_warnings() # 禁用警告

today = datetime.datetime.now().strftime("%Y-%m-%d")


def update_today(data: list = []):
    """更新today"""
    root_path = Path(__file__).absolute().parent
    data_path = root_path.joinpath("temp_data.json")
    today_path = root_path.joinpath("today.md")
    archive_path = root_path.joinpath(f'archive/{today.split("-")[0]}/{today}.md')

    if not data and data_path.exists():
        with open(data_path, "r", encoding="utf-8") as f1:
            data = json.load(f1)

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with open(today_path, "w+", encoding="utf-8") as f1, open(
        archive_path, "w+", encoding="utf-8"
    ) as f2:
        content = f"# 每日安全资讯（{today}）\n\n"
        for item in data:
            ((feed, value),) = item.items()
            content += f"- {feed}\n"
            for title, url in value.items():
                content += f"  - [{title}]({url})\n"
        f1.write(content)
        f2.write(content)
    logger.info(f"Updated today files: {today_path} and {archive_path}")


"""更新订阅源文件"""


def update_rss(config: dict, proxy_url=""):
    """根据配置文件自动扫描 rss 文件夹并更新 RSS 源"""
    proxy = (
        {"http": proxy_url, "https": proxy_url}
        if proxy_url
        else {"http": None, "https": None}
    )

    # 从配置文件获取 RSS 文件夹路径
    rss_folder = Path(config.get("pathname", root_path.joinpath("rss")))
    if not rss_folder.exists():
        rss_folder.mkdir(parents=True)
        logger.info(f"Created RSS folder: {rss_folder}")

    results = []
    logger.info(
        f'Start parsing {len(list(rss_folder.glob("*.xml")) + list(rss_folder.glob("*.opml")))} RSS files'
    )
    # 扫描 rss 文件夹下的所有 xml/opml 文件
    for rss_file in rss_folder.glob("*.xml"):
        key = rss_file.stem
        try:
            # 解析 xml 文件获取 feed url
            feed = feedparser.parse(rss_file)
            if feed.feed.get("link"):
                r = requests.get(feed.feed.link, proxies=proxy)
                if r.status_code == 200:
                    with open(rss_file, "w+", encoding="utf-8") as f:
                        f.write(r.text)
                    logger.success(f"Updated: {key}")
                    results.append({key: rss_file})
                else:
                    logger.warning(f"Update failed, using old file: {key}")
                    results.append({key: rss_file})
            else:
                logger.info(f"Local file (no link): {key}")
        except Exception as e:
            logger.error(f"Failed to parse: {key} - {str(e)}")

    # 解析 opml 文件
    for opml_file in rss_folder.glob("*.opml"):
        try:
            feeds = listparser.parse(opml_file.read_text())
            for feed in feeds.feeds:
                key = feed.title
                rss_path = rss_folder.joinpath(f"{key}.xml")

                r = requests.get(feed.url, proxies=proxy)
                if r.status_code == 200:
                    with open(rss_path, "w+", encoding="utf-8") as f:
                        f.write(r.text)
                    logger.success(f"Updated: {key}")
                    results.append({key: rss_path})
                else:
                    logger.error(f"Update failed: {key}")
        except Exception as e:
            logger.error(f"Failed to parse OPML: {opml_file.name} - {str(e)}")

    return results


def parseThread(conf: dict, url: str, proxy_url="", stop_event=None, pbar=None):
    """获取文章线程"""

    def filter(title: str):
        """过滤文章"""
        for i in conf["exclude"]:
            if i in title:
                return False
        return True

    proxy = (
        {"http": proxy_url, "https": proxy_url}
        if proxy_url
        else {"http": None, "https": None}
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    title = ""
    result = {}
    is_error = False
    try:
        # 检查是否需要停止
        if stop_event and stop_event.is_set():
            return url, {}

        # 设置较短的超时时间以便及时响应中断
        r = requests.get(url, timeout=5, headers=headers, verify=False, proxies=proxy)

        # 再次检查是否需要停止
        if stop_event and stop_event.is_set():
            return url, {}

        r = feedparser.parse(r.content)
        title = r.feed.title or url

        if pbar:
            pbar.set_description(f"Processing: {title[:10]}...")

        for entry in r.entries:
            # 定期检查是否需要停止
            if stop_event and stop_event.is_set():
                return url, {}

            d = entry.get("published_parsed") or entry.get("updated_parsed")
            if not d:
                continue
            yesterday = datetime.date.today() + datetime.timedelta(-1)
            pubday = datetime.date(d[0], d[1], d[2])
            if pubday == yesterday and filter(entry.title):
                item = {entry.title: entry.link}
                result |= item
        # logger.success(f"Fetched:[{title}]:{url}\t{len(result.values())}/{len(r.entries)}")
        if pbar:
            pbar.update(1)
    except Exception as e:
        title = url
        result = {}
        is_error = True
        if pbar:
            pbar.update(1)

    return title, result, is_error


async def init_bot(conf: dict, proxy_url=""):
    """初始化机器人
    根据toml配置文件初始化不同类型的机器人

    Args:
        conf (dict): toml配置文件中的bot配置部分
        proxy_url (str, optional): 代理地址. Defaults to ''.

    Returns:
        list: 初始化成功的bot列表
    """
    bots = []
    for name, config in conf.items():
        # 只处理启用的bot
        if not config["enabled"]:
            continue

        # 获取bot的key,优先使用环境变量
        key = os.getenv(config["secrets"]) or config["key"]

        try:
            # 根据不同类型初始化bot
            if name == "mail":
                # 邮件bot需要额外的收件人配置
                receiver = os.getenv(config["secrets_receiver"]) or config["receiver"]
                bot = globals()[f"{name}Bot"](
                    config["address"], key, receiver, config["from"], config["server"]
                )
                bots.append(bot)

            elif name == "qq":
                # QQ bot需要启动服务器
                bot = globals()[f"{name}Bot"](config["group_id"])
                if await bot.start_server(config["qq_id"], key):
                    bots.append(bot)

            elif name == "telegram":
                # Telegram bot需要测试连接
                bot = globals()[f"{name}Bot"](key, config["chat_id"], proxy_url)
                if await bot.test_connect():
                    bots.append(bot)

            else:
                # 其他类型的bot
                bot = globals()[f"{name}Bot"](key, proxy_url)
                bots.append(bot)

        except Exception as e:
            logger.error(f"Failed to initialize {name} bot: {str(e)}")

    return bots


def init_rss(conf: dict, update: bool = False, proxy_url=""):
    """初始化订阅源"""
    if not conf.get("enabled", True):
        logger.warning("RSS feature is disabled")
        return []

    # 获取RSS文件夹路径
    rss_folder = Path(conf.get("pathname", root_path.joinpath("rss")))
    if not rss_folder.exists():
        rss_folder.mkdir(parents=True)
        logger.info(f"Created RSS folder: {rss_folder}")

    rss_list = []
    if update:
        if rss := update_rss({"pathname": rss_folder}, proxy_url):
            rss_list.extend(rss)
    else:
        # 扫描文件夹下的所有xml和opml文件
        files = list(rss_folder.glob("*.xml")) + list(rss_folder.glob("*.opml"))
        logger.info(f"Found {len(files)} RSS files")
        for file in files:
            rss_list.append({"rss": file})

    # 合并相同链接
    feeds = []
    for rss in rss_list:
        ((_, value),) = rss.items()
        try:
            # 读取本地文件
            with open(value, encoding="utf-8") as f:
                content = f.read()

            # 解析feed
            rss = listparser.parse(content)
            for feed in rss.feeds:
                url = feed.url.strip().rstrip("/")
                # 标准化url
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                # 检查重复
                if url not in feeds:
                    feeds.append(url)

        except Exception as e:
            logger.error(f"Failed to parse: {value}")
            logger.exception(e)

    logger.info(f"{len(feeds)} feeds")
    return feeds


def cleanup():
    """结束清理"""
    # qqBot.kill_server()
    logger.info("Cleaning up...")
    for task in asyncio.all_tasks():
        if task != asyncio.current_task():
            task.cancel()
    pass


async def job(args):
    """定时任务"""
    stop_event = threading.Event()
    executor = ThreadPoolExecutor(100)
    try:
        print(f'{pyfiglet.figlet_format("yarb")}\nRun Date: {today}')

        global root_path
        root_path = Path(__file__).absolute().parent
        if args.config:
            config_path = Path(args.config).expanduser().absolute()
        else:
            config_path = root_path.joinpath("config.toml")
        with open(config_path, encoding="utf-8") as f:
            conf = toml.load(f)
        proxy_rss = conf["proxy"]["url"] if conf["proxy"]["rss"] else ""
        feeds = init_rss(conf["rss"], args.update, proxy_rss)

        results = []
        if args.test:
            # 测试数据
            results.extend(
                {f"test{i}": {Pattern.create(i * 500): "test"}} for i in range(1, 3)
            )
        else:
            # 获取文章
            articles = 0
            fails = 0
            futures = []
            try:
                total_feeds = len(feeds)
                with tqdm(
                    total=total_feeds,
                    desc="RSS source processing progress",
                    unit="feed",
                    postfix={"fails": fails, "articles": articles},
                    ncols=100,
                    position=0,
                    leave=True,
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]| {postfix}",
                ) as pbar:
                    futures = [
                        executor.submit(
                            parseThread,
                            conf["keywords"],
                            url,
                            proxy_rss,
                            stop_event,
                            pbar,
                        )
                        for url in feeds
                    ]

                    # 等待所有任务完成
                    for future in as_completed(futures):
                        if stop_event.is_set():
                            break
                        try:
                            title, result, is_error = future.result(timeout=5)
                            if is_error:
                                fails += 1
                            if result:
                                articles += len(result.values())
                                results.append({title: result})
                            pbar.set_postfix({"fails": fails, "articles": articles})
                        except Exception as e:
                            logger.error(f"Task execution error: {str(e)}")

                # 确保所有任务完成后再关闭线程池
                executor.shutdown(wait=True)

                if not stop_event.is_set():
                    logger.success(
                        f"Processing completed: {len(results)} feeds, {articles} articles"
                    )

                    # 更新today
                    update_today(results)

                    # 推送文章
                    proxy_bot = conf["proxy"]["url"] if conf["proxy"]["bot"] else ""
                    bots = await init_bot(conf["bot"], proxy_bot)
                    for bot in bots:
                        await bot.send(bot.parse_results(results))

            except KeyboardInterrupt:
                logger.warning("Received interrupt signal, stopping all tasks...")
                stop_event.set()
                raise
            except Exception as e:
                logger.error(f"Execution error: {str(e)}")
                raise
            finally:
                # 确保清理所有任务
                stop_event.set()
                for future in futures:
                    future.cancel()
                executor.shutdown(wait=False)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, cleaning up...")
        stop_event.set()
        cleanup()
        executor.shutdown(wait=False)
        sys.exit(0)
    except Exception as e:
        logger.error(f"Execution error: {str(e)}")
        # logger.exception(e)
        cleanup()
        executor.shutdown(wait=False)
        sys.exit(1)
    finally:
        cleanup()
        executor.shutdown(wait=False)


def argument():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update", help="Update RSS config file", action="store_true", required=False
    )
    parser.add_argument(
        "--cron",
        help='Execute scheduled tasks every day (eg:"11:00")',
        type=str,
        required=False,
    )
    parser.add_argument(
        "--config", help="Use specified config file", type=str, required=False
    )
    parser.add_argument("--test", help="Test bot", action="store_true", required=False)
    return parser.parse_args()


async def main():
    args = argument()
    try:
        if args.cron:
            schedule.every().day.at(args.cron).do(job, args)
            while True:
                schedule.run_pending()
                await asyncio.sleep(1)
        else:
            await job(args)
    except KeyboardInterrupt:
        logger.info("Program terminated")
        sys.exit(0)
    finally:
        cleanup()


if __name__ == "__main__":
    asyncio.run(main())

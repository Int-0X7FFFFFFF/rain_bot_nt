import datetime
from .models.account import Account
from .models.daily_statistic import PlayerDailyStatistic
from .config import Config
from nonebot import get_plugin_config
from aiowpi import WPIClient, WOWS_ASIA, WOWS_EU, WOWS_NA, WOWS_RU
from aiowpi.error import WPIError
import asyncio
import pytz
from nonebot import logger
from aiohttp.client_exceptions import ClientConnectionError
from nonebot_plugin_apscheduler import scheduler
from apscheduler.triggers.cron import CronTrigger
from collections import defaultdict
from .wows_models import User as Player
from typing import Callable

api_config = get_plugin_config(Config).wows_api
db_config = get_plugin_config(Config).db_config

Server2url = [WOWS_ASIA, WOWS_RU, WOWS_EU, WOWS_NA]
timezone = pytz.timezone("Asia/Shanghai")


@scheduler.scheduled_job(
    CronTrigger(hour=8, minute=0, timezone=timezone), id="clan_name_update"
)
async def update_clan_tags():
    logger.info("start_update_clan_tags")
    accounts = await Account.all().values(
        "id", "account_id", "server", "clan_tag", "nickname"
    )  # 获取账户数据
    wpi = WPIClient(api_config.get_application_id(), 5)
    updated_accounts = []  # 用来存储更新后的Account实例

    async with asyncio.TaskGroup() as tg:
        for account in accounts:
            tg.create_task(
                updata_account_clan_tag_and_name(account, wpi, updated_accounts)
            )

    # 批量更新数据库
    if updated_accounts:
        await Account.bulk_update(updated_accounts, fields=["clan_tag", "nickname"])
    logger.success(f"update player clans successful: {len(updated_accounts)}")


# 更新单个account的clan_tag
async def updata_account_clan_tag_and_name(account, wpi, updated_accounts, retry=0):
    if retry > 5:
        aid = account["account_id"]
        logger.error(f"try too many times {aid} ")
    try:
        server = account["server"]
        account_id = account["account_id"]
        player_clan = (await wpi.clans.account_info(Server2url[server], account_id))[
            0
        ]  # 获取玩家的clan信息
        # logger.info(player_clan)
        clan_tag = None
        nickname = None
        if player_clan and player_clan["clan_id"]:
            clan_details = await wpi.clans.details(
                Server2url[server], player_clan["clan_id"]
            )  # 获取clan详情
            clan_tag = (
                clan_details[0]["tag"]
                if clan_details and clan_details[0].get("tag")
                else None
            )
            nickname = player_clan["account_name"]
        if (
            clan_tag != account["clan_tag"] or nickname != account["nickname"]
        ):  # 如果clan_tag有变化
            account_instance = await Account.get(
                id=account["id"]
            )  # 获取数据库中对应的Account实例
            # logger.info(f'update_player: {account_instance.account_id}, clan_tag: {clan_tag}')
            if clan_tag:
                account_instance.clan_tag = clan_tag  # 更新clan_tag
            if nickname:
                account_instance.nickname = nickname
            updated_accounts.append(
                account_instance
            )  # 将更新过的Account实例添加到列表中
    except ClientConnectionError:
        aid = account["account_id"]
        logger.warning(f"retry {retry} times: {aid} ")
        await updata_account_clan_tag_and_name(
            account, wpi, updated_accounts, retry + 1
        )
    except WPIError as e:
        if e.code == 407:
            aid = account["account_id"]
            logger.warning(f"retry {retry} times: {aid} ")
            await updata_account_clan_tag_and_name(
                account, wpi, updated_accounts, retry + 1
            )


async def retry_request(
    func: Callable,
    *args,
    max_retries: int = 5,
    retry_interval: float = 1,
    retry_count: int = 0,
    **kwargs,
):
    """
    通用的API请求重试方法

    :param func: 需要重试的函数
    :param args: 传递给函数的参数
    :param max_retries: 最大重试次数
    :param retry_interval: 重试间隔（秒）
    :param retry_count: 当前重试次数
    :param kwargs: 传递给函数的关键字参数
    :return: 函数的返回值
    """
    if retry_count >= max_retries:
        logger.error(f"Max retries reached for {func.__name__} with args {args}")
        return []

    try:
        result = await func(*args, **kwargs)  # 调用原始函数
        return result
    except ClientConnectionError:
        logger.warning(
            f"Retry {retry_count + 1} failed due to connection error, for {func.__name__} with args {args}"
        )
        await asyncio.sleep(retry_interval)  # 等待一定时间后重试
        return await retry_request(
            func,
            *args,
            max_retries=max_retries,
            retry_interval=retry_interval,
            retry_count=retry_count + 1,
            **kwargs,
        )
    except WPIError as e:
        if e.code == 407:
            logger.warning(
                f"Retry {retry_count + 1} failed due to WPIError (code 407), for {func.__name__} with args {args}"
            )
            await asyncio.sleep(retry_interval)
            return await retry_request(
                func,
                *args,
                max_retries=max_retries,
                retry_interval=retry_interval,
                retry_count=retry_count + 1,
                **kwargs,
            )
        else:
            logger.error(f"WPIError occurred with code {e.code}: {e.message}")
            return []
    except Exception as e:
        logger.error(f"Unexpected error during {func.__name__}: {e}")
        raise e


@scheduler.scheduled_job(
    CronTrigger(hour=3, minute=0, timezone=timezone), id="update_ships"
)
async def update_player_daily_statistic():
    accounts = await Account.all().values("account_id", "server")
    wpi = WPIClient(api_config.get_application_id(), 3)
    detail_tasks = []
    stat_tasks = []
    server2account_ids = defaultdict(list)
    for account in accounts:
        account_id = account["account_id"]
        server = Server2url[account["server"]]
        server2account_ids[server].append(account_id)
    curr_date = datetime.date.today()
    async with asyncio.TaskGroup() as tg:
        for server, account_ids in server2account_ids.items():
            detail_tasks.append(
                tg.create_task(
                    retry_request(wpi.player.personal_data, server, account_ids)
                )
            )
            stat_tasks.append(
                tg.create_task(
                    retry_request(wpi.warships.statistics, server, account_ids)
                )
            )

    aid2data = defaultdict(dict)
    for task in detail_tasks:
        for detail in task.result():
            if detail:
                aid = detail['account_id']
                aid2data[aid]['detail'] = detail
    for task in stat_tasks:
        for stat in task.result():
            if stat and stat[0]:
                aid = stat[0]['account_id']
                aid2data[aid]['stat'] = stat

    player_daily_statistics = []

    for aid, data in aid2data.items():
        detail = data.get('detail', None)
        stat = data.get('stat', None)
        if not detail and stat:
            continue
        player = Player()
        player.init_user(detail, stat, -1, None, "")
        await player.async_init(stat)
        player_daily_statistics.extend(
            await PlayerDailyStatistic.create_from_player(player, curr_date)
        )

    await PlayerDailyStatistic.bulk_create(
        player_daily_statistics,
        on_conflict=["account_id", "ship_id", "last_battle_at"],
        update_fields=["date"],
    )

# -*- coding: UTF-8 -*-
"""
指令解析器
"""
from nonebot.rule import startswith, is_type
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Bot, MessageSegment
from nonebot import get_plugin_config
from nonebot.plugin import on_message
from nonebot.exception import MatcherException
from .config import Config
from .interrupt import add_player_waiter, wait_me, wait_account_id
from tortoise import Tortoise
from nonebot import logger
from .wows_img import gen_player_image_by_account_id, get_me_recent_image
import aiohttp
from aiohttp.client_exceptions import ClientConnectorError
from .wows_auto import update_player_daily_statistic
from .models.daily_statistic import PlayerDailyStatistic
import datetime

plugin_config = get_plugin_config(Config).wows_api
db_config = get_plugin_config(Config).db_config


async def init_db():
    await Tortoise.init(
        db_url=db_config.conn,
        modules={"models": ["wows_core.models.account", "wows_core.models.daily_statistic"]},
    )
    # Generate the schema
    await Tortoise.generate_schemas()
    logger.success("init DB success")


wows = on_message(
    rule=startswith("wows") & is_type(GroupMessageEvent), priority=1, block=False
)

servers = {
    "asia": 0,
    "ru": 1,
    "eu": 2,
    "na": 3,
}

async def get_args(messages: list[MessageSegment]) -> list[str]:
    args = []
    for message in messages:
        if message.type == 'text':
            args.extend(message.data['text'].split())
        elif message.type == 'at':
            args.append(message)
    return args[1:]

@wows.handle()
async def handler(bot: Bot, event: GroupMessageEvent):
    await init_db()
    try:
        args = await get_args(event.original_message)
        if not args:
            return
        nagrs = len(args)
        logger.debug(args)
        match nagrs:
            case 1:
                """当指令长度为1时只有 wows me 和 wows exboom, wows help 3种情况"""
                match args[0]:
                    case "me":
                        status, account_id, server, clan_tag = await wait_me(wows, event.user_id)
                        if status:
                            img = await gen_player_image_by_account_id(
                                account_id, server, clan_tag
                            )
                            await wows.finish(img)
                    case "help":
                        raise NotImplementedError
                    case "tt":
                        await tt()
                    case _:
                        if isinstance(args[0], MessageSegment) and args[0].type == 'at':
                            target_id = args[0].data['qq']
                            status, account_id, server, clan_tag = await wait_me(wows, target_id)
                            if status:
                                img = await gen_player_image_by_account_id(
                                    account_id, server, clan_tag
                                )
                                await wows.finish(img)
                        else:
                            status, account_id, server = await wait_account_id(wows, args[0])
                            if status:
                                img = await gen_player_image_by_account_id(
                                    account_id, server
                                )
                                await wows.finish(img)
            case 2:
                """
                当指令长度为2时
                会出现wows me/@ recent 和 wows asia exboom 和新的 wows me/@ recents
                wows me rank
                wows exboom rank
                """
                match args[0]:
                    case "me":
                        if args[1] == 'recent':
                            status, account_id, server, clan_tag = await wait_me(wows, event.user_id)
                            if status:
                                if img := await get_me_recent_image(account_id, server, clan_tag=clan_tag):
                                    await wows.finish(img)
                                else:
                                    await wows.finish('找不到数据~')
                        elif args[1] == 'recents':
                            raise NotImplementedError
                    case "remove":
                        raise NotImplementedError
                    case "add":
                        if args[1]:
                            await add_player_waiter(wows, args[1], event)
                        else:
                            await wows.finish("无法处理指令: " + str(args))
                    case _:
                        if isinstance(args[0], MessageSegment) and args[0].type == 'at':
                            target_id = args[0].data['qq']
                            if args[1] == 'recent':
                                status, account_id, server, clan_tag = await wait_me(wows, target_id)
                                if status:
                                    if img := await get_me_recent_image(account_id, server, clan_tag=clan_tag):
                                        await wows.finish(img)
                                    else:
                                        await wows.finish('找不到数据~')
                            elif args[1] == 'recents':
                                raise NotImplementedError
                        else:
                            status, account_id, server = await wait_account_id(wows, args[0])
                            if status:
                                img = await gen_player_image_by_account_id(
                                    account_id, server
                                )
                                await wows.finish(img)
            case 3:
                """
                当指令为3时可能出现
                wows me ship 大胆
                wows exboom ship 大胆
                wows asia exboom rank
                wows me recent n
                wows target recent n
                """
                match args[0]:
                    case "me":
                        if args[1] == 'recent':
                            date = datetime.date.today() - datetime.timedelta(days=int(args[2]))
                            status, account_id, server, clan_tag = await wait_me(wows, event.user_id)
                            if status:
                                if img := await get_me_recent_image(account_id, server, clan_tag=clan_tag, date=date):
                                    await wows.finish(img)
                                else:
                                    await wows.finish('找不到数据~')
                            pass
                        raise NotImplementedError
                    case _:
                        raise NotImplementedError
            case 4:
                """
                当指令为4时可能出现
                wows asia exboom ship 大胆
                """
                server = servers.get(args[0], None)
                if not server:
                    return
                raise NotImplementedError
            case _:
                return
    # None bot 使用异常中断函数执行
    except MatcherException:
        raise
    except NotImplementedError:
        await wows.finish("前面的区域以后再来探索吧~")
    except ClientConnectorError as e:
        await wows.finish("网络问题，无法连接到WG服务器。请稍后重试。")
    except aiohttp.ClientResponseError as e:
        await wows.finish(f"请求出错: {e.status} {e.message}")
    except Exception as e:
        await wows.send(str(e))
        raise
    finally:
        await Tortoise.close_connections()

async def tt():
    await update_player_daily_statistic()
    pass
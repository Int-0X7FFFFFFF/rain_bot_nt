"""
中断控制器
"""

import asyncio
from nonebot_plugin_waiter import waiter
from .config import Config
from nonebot import get_plugin_config
from aiowpi import WPIClient, WOWS_ASIA, WOWS_EU, WOWS_NA, WOWS_RU
from nonebot.internal.matcher import Matcher
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.adapters import Event
from .models.account import Account, UserInfo
from tortoise.exceptions import IntegrityError
from typing import Tuple

plugin_config = get_plugin_config(Config)

Server = [0, 2, 3]
Server2str = ["亚服", "毛服", "欧服", "美服"]
Server2url = [WOWS_ASIA, WOWS_RU, WOWS_EU, WOWS_NA]


async def add_player_waiter(
    matcher: Matcher, keyword: str, tragger_event: GroupMessageEvent
) -> None:
    wpi_client = WPIClient(plugin_config.wows_api.get_application_id(), 10, 1)
    await matcher.send("开始查找玩家账号")

    # 存储玩家信息：昵称, account_id, 服务器
    player_info = []
    account2server = {}
    msg = "找到以下几个账号\n"
    idx = 0
    parms = [idx, msg]

    # 使用 asyncio.TaskGroup 来并发查找玩家
    async with asyncio.TaskGroup() as tg:
        for server in Server:
            tg.create_task(
                fetch_players(
                    wpi_client, server, keyword, player_info, account2server, parms
                )
            )

    # 拼接消息
    msg = parms[1]
    msg += "\n选一个吧"
    idx = parms[0]
    if idx == 0:
        await matcher.finish("找不到呢，检查拼写试试？")
    else:
        await matcher.send(msg)

    # 等待用户选择
    account_select = None

    @waiter(waits=["message"], keep_session=True)
    async def check(event: Event):
        return event.get_plaintext()

    async for resp in check(
        timeout=30, retry=3, prompt="再想想改怎么回答呢~ 剩余次数：{count}"
    ):
        if resp is None:
            await matcher.send("要不想好了再来问呢~")
            break
        if not resp.isdigit() or int(resp) < 0 or int(resp) >= len(player_info):
            continue
        account_select = player_info[int(resp)]["account_id"]
        break
    else:
        await matcher.send("输入失败")

    if account_select is None:
        return

    # 获取玩家选择的 account_id 和对应服务器
    selected_player = next(
        player for player in player_info if player["account_id"] == account_select
    )
    sender_id = tragger_event.user_id
    clan_tag = None
    server = selected_player["server"]
    if account_clan := (
        await wpi_client.clans.account_info(
            Server2url[server], selected_player["account_id"]
        )
    )[0]:
        if clan_detail := (
            await wpi_client.clans.details(Server2url[server], account_clan["clan_id"])
        )[0]:
            clan_tag = clan_detail["tag"]

    try:
        # 创建或更新 Account 记录
        account, created = await Account.get_or_create(
            account_id=selected_player["account_id"],
            server=selected_player["server"],
            defaults={"nickname": selected_player["nickname"], "clan_tag": clan_tag},
        )

        # 如果 Account 已经存在，检查是否需要更新
        if not created:
            # 更新已有 Account 信息（如果需要的话）
            account.nickname = selected_player["nickname"]
            account.clan_tag = clan_tag
            await account.save()

        # 创建或更新 UserInfo 记录
        _, created = await UserInfo.get_or_create(
            qid=sender_id, defaults={"account": account}  # sender_id 作为 qid
        )
        if not created:
            raise IntegrityError

        # 返回绑定成功的消息
        nickname = selected_player["nickname"]
        await matcher.finish(f"绑定成功, {nickname}, {Server2str[server]}")

    except IntegrityError as e:
        # 捕获 IntegrityError 异常，处理数据库唯一约束错误
        await matcher.finish("绑定失败，数据库约束错误。应该已经绑定过了。")

    finally:
        pass

async def immdeitly_update_player(account_id:int, server:int):
    pass


async def fetch_players(
    wpi_client, server, keyword, player_info, account2server, prams
) -> None:
    # 异步查找玩家信息
    players = await wpi_client.player.serch(Server2url[server], search=keyword, limit=3)
    for player in players:
        # 存储玩家信息：昵称、account_id 和 服务器
        player_info.append(
            {"nickname": player[0], "account_id": player[1], "server": server}
        )
        account2server[player[1]] = server

        # 更新消息
        tmp_str = f"\n[{prams[0]}]: {player[0]}, {player[1]}, {Server2str[server]}"
        prams[1] += tmp_str
        prams[0] += 1


async def wait_me(matcher: Matcher, sender_id) -> Tuple[bool, int]:
    # accounts = await Account.filter(qid=sender_id).values(
    #     "account_id", "server", "nickname"
    # )
    accounts = (
        await UserInfo.filter(qid=sender_id)
        .prefetch_related("account")
        .values("account__account_id", "account__server", "account__clan_tag", "account__nickname")
    )
    if len(accounts) == 1:
        return (
            True,
            accounts[0]["account__account_id"],
            accounts[0]["account__server"],
            accounts[0]["account__clan_tag"],
        )
    elif len(accounts) < 0:
        await matcher.finish("? 试试先用 wows add 游戏内名称 绑定一下~")
        return False, None, None
    msg = """找到多个账号\n"""
    for index, account in enumerate(accounts):
        msg += f"[{index}]: {account['account__nickname']}  {Server2str[account['account__server']]}\n"
    msg += "选一个吧"
    await matcher.send(msg)

    @waiter(waits=["message"], keep_session=True)
    async def check(event: Event):
        return event.get_plaintext()

    async for resp in check(
        timeout=30, retry=3, prompt="再想想改怎么回答呢~ 剩余次数：{count}"
    ):
        if resp is None:
            await matcher.send("等待超时")
            break
        if not resp.isdigit() or int(resp) < 0 or int(resp) >= len(accounts):
            continue
        account_select = accounts[int(resp)]
        break
    else:
        await matcher.send("输入失败")

    if account_select is None:
        return False, None, None
    return (
        True,
        account_select["account__account_id"],
        account_select["account__server"],
        account_select["account__clan_tag"],
    )

async def wait_account_id(matcher: Matcher, keyword: str, server_list=Server):
    wpi_client = WPIClient(plugin_config.wows_api.get_application_id(), 10, 1)
    # 存储玩家信息：昵称, account_id, 服务器
    player_info = []
    account2server = {}
    msg = "找到以下几个账号\n"
    idx = 0
    parms = [idx, msg]
    # 使用 asyncio.TaskGroup 来并发查找玩家
    async with asyncio.TaskGroup() as tg:
        for server in server_list:
            tg.create_task(
                fetch_players(
                    wpi_client, server, keyword, player_info, account2server, parms
                )
            )

    # 拼接消息
    msg = parms[1]
    msg += "\n选一个吧"
    idx = parms[0]
    account_select = None
    if idx == 0:
        await matcher.finish("找不到呢，检查拼写试试？")
    elif idx == 1:
        account_select = player_info[0]["account_id"]
    else:
        await matcher.send(msg)
    
        # 等待用户选择

        @waiter(waits=["message"], keep_session=True)
        async def check(event: Event):
            return event.get_plaintext()

        async for resp in check(
            timeout=30, retry=3, prompt="再想想改怎么回答呢~ 剩余次数：{count}"
        ):
            if resp is None:
                await matcher.send("要不想好了再来问呢~")
                break
            if not resp.isdigit() or int(resp) < 0 or int(resp) >= len(player_info):
                continue
            account_select = player_info[int(resp)]["account_id"]
            break
        else:
            await matcher.send("输入失败")

    if account_select is None:
        return False, None, None

    # 获取玩家选择的 account_id 和对应服务器
    selected_player = next(
        player for player in player_info if player["account_id"] == account_select
    )
    server = selected_player["server"]
    account_id = selected_player["account_id"]
    return True, account_id, server
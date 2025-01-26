import asyncio
from aiowpi import WPIClient, WOWS_ASIA, WOWS_EU, WOWS_NA, WOWS_RU
from nonebot import get_plugin_config
from .config import Config, get_cache
from .wows_models import User as Player
from .wows_models import Ship as WarShip
from .wows_models import wows_user, wows_recent
from PIL import ImageFont
import cv2 as cv
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from .models.daily_statistic import PlayerDailyStatistic
from .wows_auto import retry_request
import json

Server2url = [WOWS_ASIA, WOWS_RU, WOWS_EU, WOWS_NA]
plugin_config = get_plugin_config(Config)


async def get_image_and_font():
    WOWS_CORE_CACHE = get_cache()
    if not WOWS_CORE_CACHE.get("base_img", None):
        main_data_img = cv.imread("wows_core/components/main_data.png")
        pr_bar_img = cv.imread("wows_core/components/pr_bar.png")
        max_data_img = cv.imread("wows_core/components/max_main.png")
        recent_data_img = cv.imread("wows_core/components/recent.png")
        images = [main_data_img, pr_bar_img, max_data_img, recent_data_img]
        WOWS_CORE_CACHE["base_img"] = images
    if not WOWS_CORE_CACHE.get("fonts", None):
        font_medium = ImageFont.truetype(
            "wows_core/src/font/SourceHanSans-Heavy.otf", 40
        )
        font_heavy = ImageFont.truetype(
            "wows_core/src/font/SourceHanSans-Heavy.otf", 48
        )
        font_medium_32 = ImageFont.truetype(
            "wows_core/src/font/SourceHanSans-Heavy.otf", 32
        )
        fonts = [font_medium, font_heavy, font_medium_32]
        WOWS_CORE_CACHE["fonts"] = fonts

    return WOWS_CORE_CACHE["base_img"], WOWS_CORE_CACHE["fonts"]


async def gen_player_image_by_account_id(account_id: int, server: int, clan_tag=None):
    server_int = server
    server = Server2url[server]
    client = WPIClient(plugin_config.wows_api.get_application_id())
    async with asyncio.TaskGroup() as tg:
        player_detail = tg.create_task(client.player.personal_data(server, account_id))
        if not clan_tag:
            player_clan = tg.create_task(client.clans.account_info(server, account_id))
        player_stat = tg.create_task(client.warships.statistics(server, account_id))
    if not clan_tag:
        if player_clan := player_clan.result()[0]:
            clan_details = await client.clans.details(server, player_clan["clan_id"])
            clan_tag = clan_details[0]["tag"] if clan_details[0]["tag"] else "_NO_CLAN_"

    player_detail = player_detail.result()
    player_stat = player_stat.result()

    player = Player()
    player.init_user(player_detail[0], player_stat[0], server_int, None, clan_tag if clan_tag else "_NO_CLAN_")
    await player.async_init(player_stat[0])
    base_img, fonts = await get_image_and_font()
    img = await wows_user(player, base_img, fonts)
    return MessageSegment.image(img)

async def get_me_recent_image(account_id: int, server: int, date=None, clan_tag=None):
    server_int = server
    server = Server2url[server]
    client = WPIClient(plugin_config.wows_api.get_application_id())
    async with asyncio.TaskGroup() as tg:
        player_detail = tg.create_task(retry_request(client.player.personal_data, server, account_id))
        if not clan_tag:
            player_clan = tg.create_task(retry_request(client.clans.account_info, server, account_id))
        player_stat = tg.create_task(retry_request(client.warships.statistics, server, account_id))
        db_player = tg.create_task(PlayerDailyStatistic.get_player_from_db(account_id, date))
    if not clan_tag:
        if player_clan := player_clan.result()[0]:
            clan_details = await retry_request(client.clans.details, server, player_clan["clan_id"])
            clan_tag = clan_details[0]["tag"] if clan_details[0]["tag"] else "_NO_CLAN_"

    player_detail = player_detail.result()
    player_stat = player_stat.result()
    db_player = db_player.result()

    if not db_player:
        return

    player = Player()
    player.init_user(player_detail[0], player_stat[0], server_int, None, clan_tag if clan_tag else "_NO_CLAN_")
    await player.async_init(player_stat[0])
    recent_player = player - db_player
    await recent_player.init_pr_sub()
    base_img, fonts = await get_image_and_font()
    img = await wows_recent(recent_player, base_img, fonts)
    return MessageSegment.image(img)

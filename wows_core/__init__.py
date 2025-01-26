from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot import require

require("nonebot_plugin_waiter")
require("nonebot_plugin_apscheduler")

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="wows_core",
    description="",
    usage="",
    config=Config,
)

from .cmd_handler import *
from .wows_auto import *
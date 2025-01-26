from tortoise import fields
from tortoise.models import Model
from .account import Account
from ..wows_models import User, Ship
from tortoise.functions import Min, Max
from tortoise.exceptions import DoesNotExist
import datetime


class PlayerDailyStatistic(Model):
    account: fields.ForeignKeyRelation[Account] = fields.ForeignKeyField(
        "models.Account", related_name="daily_statistics", on_delete=fields.CASCADE
    )  # Reference to Account
    ship_id: int = fields.BigIntField()  # Ship identifier
    date = fields.DateField()  # Date of the statistics
    battles: int = fields.IntField()  # Total battles
    wins: int = fields.IntField()  # Total wins
    shots: int = fields.BigIntField()  # Total shots fired
    hit: int = fields.BigIntField()  # Total hits
    damage: int = fields.IntField()  # Total damage
    frags: int = fields.IntField()  # Total frags
    survive: int = fields.IntField()  # Total survive
    xp: int = fields.BigIntField()  # Total experience points
    last_battle_at = fields.DatetimeField()

    class Meta:
        table = "player_daily_statistics"
        unique_together = (
            ("account", "ship_id", "date"),
        )  # Composite key for account, ship, and date

    @staticmethod
    async def create_from_player(player: User, curr_date=None, account=None):
        account_id = player.account_id
        curr_date = curr_date if curr_date else datetime.date.today()
        ship_list: list[Ship] = player.ship_list
        account = (
            account
            if account
            else (await Account.filter(account_id=account_id).first())
        )
        statistic_list = [
            PlayerDailyStatistic(
                account_id=account.id,
                ship_id=ship.ship_id,
                date=curr_date,
                battles=ship.battles,
                wins=ship.wins,
                shots=ship.shots,
                hit=ship.hits,
                damage=ship.damage_dealt,
                frags=ship.frags,
                survive=ship.survived_battles,
                xp=ship.xp,
                last_battle_at=ship.last_battle_time_raw,
            )
            for ship in ship_list
        ]
        return statistic_list

    @staticmethod
    async def get_recent_date(account_id: int):
        try:
            # 查找给定 account_id 的所有记录，按 date 降序排序（最接近的在前面）
            recent_statistic = (
                await PlayerDailyStatistic.filter(account_id=account_id)
                .order_by("-date")
                .first()
            )

            # 如果找到了记录，返回最近的日期
            if recent_statistic:
                return recent_statistic.date
            else:
                return None  # 如果没有找到记录，返回 None
        except DoesNotExist:
            return None  # 如果找不到记录，也返回 None

    @staticmethod
    async def get_player_from_db(account_id: int, date=None):
        if account := await Account.get_or_none(account_id=account_id):
            date = date if date else await PlayerDailyStatistic.get_recent_date(account.id)
            if not date:
                return
            ship_stats = await PlayerDailyStatistic.filter(account_id=account_id, date=date)
            user = User()
            user.date = date
            ship_list = []
            user.battles = 0
            user.xp = 0
            user.wins = 0
            user.frags = 0
            user.shots = 0
            user.damage_dealt = 0
            user.hits = 0
            user.survived_battles = 0
            for ship in ship_stats:
                ship_id = ship.ship_id
                battles = ship.battles
                frags = ship.frags
                xp = ship.xp
                damage = ship.damage
                wins = ship.wins
                survived = ship.survive
                shots = ship.shots
                hits = ship.hit
                last_battle_time = ship.last_battle_at

                user.battles += battles
                user.xp += xp
                user.wins += wins
                user.frags += frags
                user.shots += shots
                user.hits += hits
                user.damage_dealt += damage
                user.survived_battles += survived

                ship_list.append(
                    {
                        "pvp": {
                            "battles": battles,
                            "frags": frags,
                            "damage_dealt": damage,
                            "wins": wins,
                            "xp": xp,
                            "survived_battles": survived,
                            "main_battery": {"shots": shots, "hits": hits},
                        },
                        "ship_id": ship_id,
                        "last_battle_time": last_battle_time.timestamp(),
                    }
                )

            user.update_displays()
            await user.async_init(ship_list)
            return user

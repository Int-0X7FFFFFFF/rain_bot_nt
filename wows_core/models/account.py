from tortoise import fields
from tortoise.models import Model


class Account(Model):
    id: int = fields.IntField(pk=True, auto_increment=True)  # 自增主键
    account_id: int = fields.BigIntField()  # 使用 int64 类型
    server: int = fields.BigIntField()  # 使用枚举类型映射
    nickname: str = fields.CharField(50)
    clan_tag: str = fields.CharField(50, null=True)

    class Meta:
        table = "accounts"
        unique_together = (("server", "account_id"),)  # 复合主键: server 和 account_id


class UserInfo(Model):
    qid: int = fields.BigIntField()
    account: fields.ForeignKeyRelation[Account] = fields.ForeignKeyField(
        "models.Account", on_delete=fields.CASCADE
    )

    class Meta:
        table = "user_info"
        unique_together = (("qid", "account_id"),)

    @classmethod
    async def delete_user_info(cls, qid: int):
        # 删除指定 qid 的 UserInfo
        user_info = await cls.get(qid=qid)
        account_id = user_info.account_id

        # 删除 UserInfo 记录
        await user_info.delete()

        # 检查是否有其他 UserInfo 记录依赖该 account_id
        remaining_user_info = await cls.filter(account_id=account_id).count()

        if remaining_user_info == 0:
            # 如果没有其他记录，删除 Account
            await Account.filter(id=account_id).delete()

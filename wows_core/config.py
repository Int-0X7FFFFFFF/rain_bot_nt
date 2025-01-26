from pydantic import BaseModel
import itertools


class WowsApiConfig(BaseModel):
    application_id: list[str]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__pool = itertools.cycle(self.application_id)

    def get_application_id(self):
        return next(self.__pool)


class PgDBConfig(BaseModel):
    conn: str


class Config(BaseModel):
    wows_api: WowsApiConfig
    db_config: PgDBConfig


WOWS_CORE_CACHE = {}


def get_cache():
    global WOWS_CORE_CACHE
    return WOWS_CORE_CACHE

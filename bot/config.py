import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_user_id: int
    support_group_id: int
    private_channel_id: int | None
    db_path: str
    tz: str
    stars_price: int
    stars_title: str
    stars_description: str

def load_config() -> Config:
    return Config(
        bot_token=os.environ["BOT_TOKEN"],
        admin_user_id=int(os.environ["ADMIN_USER_ID"]),
        support_group_id=int(os.environ["SUPPORT_GROUP_ID"]),
        private_channel_id=int(os.environ["PRIVATE_CHANNEL_ID"]) if os.environ.get("PRIVATE_CHANNEL_ID","").strip() else None,
        db_path=os.environ.get("DB_PATH","/data/bot.sqlite3"),
        tz=os.environ.get("TZ","Europe/Tallinn"),
        stars_price=int(os.environ.get("STARS_PRICE","199")),
        stars_title=os.environ.get("STARS_TITLE","Access 30 days"),
        stars_description=os.environ.get("STARS_DESCRIPTION","Trading bot access for 30 days"),
    )

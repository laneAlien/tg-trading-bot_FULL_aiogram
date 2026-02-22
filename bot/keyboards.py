from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def kb_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for text, cb in [
        ("🪙 Монеты", "main:coins"),
        ("📊 Режим рынка (график)", "main:regime"),
        ("⚙️ Стратегии", "main:strategies"),
        ("🎯 PROMO MODE", "main:promo"),
        ("🧯 Сорвался/Устал", "main:tilt"),
        ("✅ Чеклисты", "main:checklists"),
        ("🧾 Журнал", "main:journal"),
        ("🔒 Приватка", "main:privatka"),
        ("🆘 Поддержка", "main:support"),
        ("⭐ Доступ", "main:access"),
        ("ℹ️ Помощь", "main:help"),
    ]:
        b.button(text=text, callback_data=cb)
    b.adjust(2,2,2,2,2,1)
    return b.as_markup()

def kb_access() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📜 Дисклеймер", callback_data="access:disclaimer")
    b.button(text="✅ Я согласен", callback_data="access:disclaimer:agree")
    b.button(text="⭐ Купить 30 дней", callback_data="access:buy:30d")
    b.button(text="📌 Статус доступа", callback_data="access:status")
    b.button(text="⬅️ Назад", callback_data="nav:back:main")
    b.adjust(1,1,1,1,1)
    return b.as_markup()

def kb_support() -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    b.button(text="✉️ Создать тикет", callback_data="support:new")
    b.button(text="⬅️ Назад", callback_data="nav:back:main")
    b.adjust(1,1)
    return b.as_markup()

def kb_ticket_admin(ticket_id: int) -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    b.button(text="↩️ Ответить", callback_data=f"admin:tickets:reply:{ticket_id}")
    b.button(text="✅ Закрыть", callback_data=f"admin:tickets:close:{ticket_id}")
    b.adjust(2)
    return b.as_markup()

def kb_admin_panel() -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    b.button(text="📥 Тикеты (open)", callback_data="admin:tickets:open")
    b.button(text="📣 Рассылка", callback_data="admin:broadcast:new")
    b.button(text="➕ Whitelist добавить", callback_data="admin:whitelist:add")
    b.button(text="➖ Whitelist убрать", callback_data="admin:whitelist:remove")
    b.button(text="⬅️ Назад", callback_data="nav:back:main")
    b.adjust(2,2,1)
    return b.as_markup()

def kb_coins_menu() -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    b.button(text="📈 Топ рост", callback_data="coins:gainers")
    b.button(text="📉 Топ падение", callback_data="coins:losers")
    b.button(text="⭐ Избранное", callback_data="coins:favorites")
    b.button(text="🔎 Поиск", callback_data="coins:search")
    b.button(text="⬅️ Назад", callback_data="nav:back:main")
    b.adjust(2,2,1)
    return b.as_markup()

def kb_symbol_actions(symbol: str, is_fav: bool) -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    b.button(text="✅ Сделать активной", callback_data=f"coins:set:{symbol}")
    b.button(text=("⭐ В избранное" if not is_fav else "🗑 Удалить из избранного"), callback_data=f"coins:fav:{'add' if not is_fav else 'del'}:{symbol}")
    b.button(text="📊 График (TF)", callback_data="main:regime")
    b.button(text="⬅️ Назад", callback_data="main:coins")
    b.adjust(1,1,1,1)
    return b.as_markup()


def kb_regime_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🧠 Определить режим (15m MA30)", callback_data="regime:detect")
    b.button(text="🚫 Инвалидаторы идеи", callback_data="regime:invalidators")
    b.button(text="📊 График по TF", callback_data="regime:tfs")
    b.button(text="⬅️ Назад", callback_data="nav:back:main")
    b.adjust(1, 1, 1, 1)
    return b.as_markup()

def kb_chart_tf() -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    for tf in ["1m","5m","15m","30m"]:
        b.button(text=tf, callback_data=f"chart:tf:{tf}")
    b.button(text="⬅️ Назад", callback_data="nav:back:main")
    b.adjust(4,1)
    return b.as_markup()

def kb_journal() -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    b.button(text="➕ Добавить запись", callback_data="journal:add")
    b.button(text="🗂 Последние записи", callback_data="journal:list")
    b.button(text="⬅️ Назад", callback_data="nav:back:main")
    b.adjust(1,1,1)
    return b.as_markup()

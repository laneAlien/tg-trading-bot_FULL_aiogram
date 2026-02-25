from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_main_access_only(analytics_chat_url: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⭐ Доступ", callback_data="main:access")
    b.button(text="🔒 Получить ссылку в канал", callback_data="main:private")
    b.button(text="📌 Статус", callback_data="access:status")
    b.button(text="🆘 Поддержка", callback_data="main:support")
    if analytics_chat_url:
        b.button(text="💬 Открыть чат аналитики", url=analytics_chat_url)
    b.adjust(1)
    return b.as_markup()


def kb_access(show_agree: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📜 Дисклеймер", callback_data="access:disclaimer")
    if show_agree:
        b.button(text="✅ Я согласен", callback_data="access:disclaimer:agree")
    b.button(text="⭐ Купить 30 дней", callback_data="access:buy:30d")
    b.button(text="📌 Статус доступа", callback_data="access:status")
    b.button(text="⬅️ Назад", callback_data="nav:back:main")
    b.adjust(1)
    return b.as_markup()

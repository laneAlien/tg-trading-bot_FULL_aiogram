from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔒 Вход в закрытый канал", callback_data="main:private")
    b.button(text="⭐ Доступ", callback_data="main:access")
    b.button(text="ℹ️ Помощь", callback_data="main:help")
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

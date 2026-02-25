from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_main_access_only(analytics_chat_url: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⭐ Доступ", callback_data="main:access")
    if not analytics_chat_url:
        b.button(text="✅ Чеклисты", callback_data="main:checklists")
        b.button(text="⚙️ Стратегии", callback_data="main:strategies")
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


def kb_checklists_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🧾 Перед сделкой", callback_data="checklists:pre")
    b.button(text="📝 Post-Mortem", callback_data="checklists:post")
    b.button(text="🎯 PROMO", callback_data="checklists:promo")
    b.button(text="🧯 Safe-mode", callback_data="checklists:safe_mode")
    b.button(text="⬅️ Назад", callback_data="nav:back:main")
    b.adjust(1)
    return b.as_markup()


def kb_checklist_guide(prev_step: str | None, next_step: str | None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if prev_step:
        b.button(text="⬅️ Назад", callback_data=f"checklists:{prev_step}")
    else:
        b.button(text="⬅️ Назад", callback_data="main:checklists")
    if next_step:
        b.button(text="➡️ Следующий шаг", callback_data=f"checklists:{next_step}")
    b.button(text="📚 К меню чеклистов", callback_data="main:checklists")
    b.adjust(2, 1)
    return b.as_markup()


def kb_strategies_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📈 Spot Grid", callback_data="strategies:spot_grid")
    b.button(text="🎯 Trailing", callback_data="strategies:trailing")
    b.button(text="🌊 Swing", callback_data="strategies:swing")
    b.button(text="⚠️ Manual 1m", callback_data="strategies:manual_1m")
    b.button(text="⬅️ Назад", callback_data="nav:back:main")
    b.adjust(1)
    return b.as_markup()


def kb_strategy_guide(prev_step: str | None, next_step: str | None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if prev_step:
        b.button(text="⬅️ Назад", callback_data=f"strategies:{prev_step}")
    else:
        b.button(text="⬅️ Назад", callback_data="main:strategies")
    if next_step:
        b.button(text="➡️ Следующий шаг", callback_data=f"strategies:{next_step}")
    b.button(text="📚 К меню стратегий", callback_data="main:strategies")
    b.adjust(2, 1)
    return b.as_markup()

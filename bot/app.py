import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from aiogram.utils.markdown import hbold, hcode

from . import charts, coins, db
from .config import load_config
from .keyboards import (
    kb_access,
    kb_checklist_guide,
    kb_checklists_menu,
    kb_main_access_only,
    kb_strategies_menu,
    kb_strategy_guide,
)
from .texts import (
    CHECKLIST_POST,
    CHECKLIST_PRE,
    CHECKLIST_PROMO,
    CHECKLIST_SAFE_MODE,
    DISCLAIMER,
    STRATEGIES_MENU_TEXT,
    STRATEGY_MANUAL_1M_TEXT,
    STRATEGY_SPOT_GRID_TEXT,
    STRATEGY_SWING_TEXT,
    STRATEGY_TRAILING_TEXT,
)


def _kb_symbol_choices(symbols: list[str]):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    b = InlineKeyboardBuilder()
    for symbol in symbols:
        b.button(text=symbol, callback_data=f"coins:set:{symbol}")
    b.adjust(1)
    return b.as_markup()


def _kb_symbol_actions(symbol: str):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    b = InlineKeyboardBuilder()
    b.button(text="⭐ В избранное", callback_data=f"coins:fav:add:{symbol}")
    b.button(text="📈 График", callback_data=f"coins:chart:{symbol}")
    b.adjust(1)
    return b.as_markup()


def mk_payload(user_id: int) -> str:
    ts = int(datetime.now(timezone.utc).timestamp())
    return f"access30d:{user_id}:{ts}:{secrets.token_hex(4)}"


def _parse_dt(dt_raw: str | None) -> datetime | None:
    if not dt_raw:
        return None
    try:
        return datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
    except Exception:
        return None


async def maybe_send_expiry_notice(bot: Bot, cfg, user_id: int) -> None:
    user = await db.get_user(cfg.db_path, user_id)
    if not user or user.get("is_whitelisted") == 1:
        return

    expires_at = _parse_dt(user.get("access_until"))
    if not expires_at:
        return

    left = expires_at - datetime.now(timezone.utc)
    if left <= timedelta(0) or left > timedelta(hours=48):
        return

    reminded_at = _parse_dt(user.get("reminder_sent_at"))
    if reminded_at and datetime.now(timezone.utc) - reminded_at < timedelta(hours=20):
        return

    hours_left = max(1, int(left.total_seconds() // 3600))
    await bot.send_message(
        user_id,
        f"⏰ Подписка заканчивается через {hours_left} ч.\nПродли в разделе ⭐ Доступ.",
        reply_markup=kb_access(),
    )
    await db.mark_reminder_sent(cfg.db_path, user_id)


async def expiry_reminder_loop(bot: Bot, cfg) -> None:
    while True:
        try:
            users = await db.list_users_for_expiry_reminder(cfg.db_path, within_hours=48)
            for u in users:
                await maybe_send_expiry_notice(bot, cfg, int(u["user_id"]))
        except Exception:
            logger.exception("[reminder_loop] Unexpected error")
        await asyncio.sleep(6 * 60 * 60)


async def issue_private_channel_invite(bot: Bot, cfg, user_id: int) -> tuple[bool, str]:
    if not cfg.private_channel_id:
        return False, "PRIVATE_CHANNEL_ID не задан."

    chat_id = int(cfg.private_channel_id)
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        if member.status in {"member", "administrator", "creator"}:
            return True, "Ты уже в закрытом канале ✅"
    except Exception:
        pass

    active_invites = await db.list_active_channel_invites(cfg.db_path, user_id=user_id, chat_id=chat_id)
    for old_invite in active_invites:
        link = old_invite.get("invite_link")
        if not link:
            continue
        try:
            await bot.revoke_chat_invite_link(chat_id=chat_id, invite_link=link)
        except Exception:
            pass
        await db.mark_channel_invite_revoked(cfg.db_path, link)

    try:
        invite = await bot.create_chat_invite_link(chat_id=chat_id, member_limit=1)
    except TelegramBadRequest:
        invite = await bot.create_chat_invite_link(chat_id=chat_id)

    await db.add_channel_invite(
        cfg.db_path,
        user_id=user_id,
        chat_id=chat_id,
        invite_link=invite.invite_link,
        invite_link_name=getattr(invite, "name", None),
        expire_date=(invite.expire_date.isoformat() if getattr(invite, "expire_date", None) else None),
        member_limit=getattr(invite, "member_limit", None),
        creates_join_request=bool(getattr(invite, "creates_join_request", False)),
    )

    try:
        await bot.send_message(user_id, f"🔗 Твоя ссылка в закрытый канал:\n{invite.invite_link}")
    except Exception as e:
        return False, f"Ссылка создана, но не удалось отправить в ЛС: {e}"

    return True, "Ссылка отправлена в ЛС ✅"


async def ensure_access(cfg, cq: CallbackQuery) -> bool:
    ok = await db.is_access_active(cfg.db_path, cq.from_user.id)
    if ok:
        return True
    await cq.answer("Доступ не активен", show_alert=True)
    await cq.message.answer("Нужен активный доступ. Открой ⭐ Доступ.", reply_markup=kb_access())
    return False


async def run() -> None:
    cfg = load_config()
    await db.init_db(cfg.db_path)

    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    @dp.startup()
    async def on_startup():
        asyncio.create_task(expiry_reminder_loop(bot, cfg))

    @dp.message(CommandStart())
    async def start(m: Message):
        await db.upsert_user(cfg.db_path, m.from_user.id, m.from_user.username)
        await maybe_send_expiry_notice(bot, cfg, m.from_user.id)
        await m.answer(
            "🏠 Это access-бот: здесь можно оформить доступ и получить ссылку в приватный канал.\n"
            "Аналитика, режимы и гайды вынесены в отдельный чат.",
            reply_markup=kb_main_access_only(cfg.analytics_chat_url),
        )

    @dp.message(Command("getchatid"))
    async def getchatid(m: Message):
        await m.answer(f"chat_id = {hcode(str(m.chat.id))}")

    @dp.message(Command("wl_add"))
    async def wl_add_do(m: Message):
        if m.from_user.id != cfg.admin_user_id:
            return

        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            return await m.answer("Использование: /wl_add <user_id>")

        target_user_id = int(parts[1].strip())
        await db.upsert_user(cfg.db_path, target_user_id, None)
        await db.set_whitelist(cfg.db_path, target_user_id, True)
        ok, msg = await issue_private_channel_invite(bot, cfg, target_user_id)
        prefix = "✅ " if ok else "⚠️ "
        await m.answer(f"{prefix}Whitelist для {target_user_id} включен. {msg}")

    @dp.callback_query(F.data == "nav:back:main")
    async def back_main(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text("🏠 Главное меню", reply_markup=kb_main_access_only(cfg.analytics_chat_url))

    @dp.callback_query(F.data == "main:support")
    async def support_main(cq: CallbackQuery):
        await cq.answer()
        await cq.message.answer(
            "🆘 Поддержка: напиши администратору или в support-группу.\n"
            f"ID support-группы: {hcode(str(cfg.support_group_id))}",
            reply_markup=kb_main_access_only(cfg.analytics_chat_url),
        )

    @dp.callback_query(F.data == "main:access")
    async def access_main(cq: CallbackQuery):
        await db.upsert_user(cfg.db_path, cq.from_user.id, cq.from_user.username)
        await cq.answer()
        await cq.message.edit_text("⭐ Доступ", reply_markup=kb_access())

    @dp.callback_query(F.data == "access:disclaimer")
    async def disclaimer(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(
            DISCLAIMER + "\n\nПодтверди согласие кнопкой ниже.",
            reply_markup=kb_access(show_agree=True),
        )

    @dp.callback_query(F.data == "access:disclaimer:agree")
    async def disclaimer_agree(cq: CallbackQuery):
        u = await db.get_user(cfg.db_path, cq.from_user.id) or {}
        if u.get("accepted_disclaimer_at"):
            await cq.answer("Уже подтверждено")
            return await cq.message.edit_text("✅ Дисклеймер уже принят.", reply_markup=kb_access())
        await db.set_disclaimer(cfg.db_path, cq.from_user.id)
        await cq.answer("Ок")
        await cq.message.edit_text("✅ Согласие сохранено. Теперь можно купить доступ.", reply_markup=kb_access())

    @dp.callback_query(F.data == "access:status")
    async def access_status(cq: CallbackQuery):
        await cq.answer()
        u = await db.get_user(cfg.db_path, cq.from_user.id) or {}
        active = await db.is_access_active(cfg.db_path, cq.from_user.id)
        status = hbold("АКТИВЕН" if active else "НЕ АКТИВЕН")
        text = [f"Статус: {status}"]
        if u.get("is_whitelisted") == 1:
            text.append("Режим: FREE (whitelist)")
        else:
            text.append(f"access_until: {hcode(str(u.get('access_until')))}")
        await maybe_send_expiry_notice(bot, cfg, cq.from_user.id)
        await cq.message.edit_text("\n".join(text), reply_markup=kb_access())

    @dp.callback_query(F.data == "access:buy:30d")
    async def access_buy(cq: CallbackQuery):
        await db.upsert_user(cfg.db_path, cq.from_user.id, cq.from_user.username)
        await cq.answer()
        u = await db.get_user(cfg.db_path, cq.from_user.id) or {}
        if not u.get("accepted_disclaimer_at"):
            return await cq.message.answer("Сначала согласись с дисклеймером ✅", reply_markup=kb_access())

        payload = mk_payload(cq.from_user.id)
        await db.create_payment(cfg.db_path, cq.from_user.id, payload, cfg.stars_price)
        prices = [LabeledPrice(label=cfg.stars_title, amount=cfg.stars_price)]
        link = await bot.create_invoice_link(
            title=cfg.stars_title,
            description=cfg.stars_description,
            payload=payload,
            currency="XTR",
            prices=prices,
        )
        await cq.message.answer(
            f"⭐ Доступ на 30 дней: {hbold(str(cfg.stars_price))} Stars\n\nОплатить: {link}",
            reply_markup=kb_access(),
        )

    @dp.pre_checkout_query()
    async def pre_checkout(pre: PreCheckoutQuery):
        await bot.answer_pre_checkout_query(pre.id, ok=True)

    @dp.message(F.successful_payment)
    async def successful_payment(m: Message):
        sp = m.successful_payment
        if sp.currency != "XTR":
            return
        payload = sp.invoice_payload
        p = await db.get_payment(cfg.db_path, payload)
        if not p or p.get("status") == "paid":
            return
        if int(sp.total_amount) != int(p["stars_amount"]):
            return

        await db.mark_payment_paid(cfg.db_path, payload)
        until = await db.grant_access_30d(cfg.db_path, m.from_user.id)
        invite_ok, invite_msg = await issue_private_channel_invite(bot, cfg, m.from_user.id)
        invite_line = f"\n{('✅' if invite_ok else '⚠️')} {invite_msg}"
        await m.answer(
            "✅ Оплата получена. Доступ активен на 30 дней.\n"
            f"Подписка до: {hcode(until[:19])}{invite_line}",
            reply_markup=kb_main_access_only(cfg.analytics_chat_url),
        )

    @dp.callback_query(F.data == "main:checklists")
    async def checklists_main(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text("✅ Чеклисты", reply_markup=kb_checklists_menu())

    @dp.callback_query(F.data == "checklists:pre")
    async def checklists_pre(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(
            CHECKLIST_PRE,
            reply_markup=kb_checklist_guide(prev_step=None, next_step="post"),
        )

    @dp.callback_query(F.data == "checklists:post")
    async def checklists_post(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(
            CHECKLIST_POST,
            reply_markup=kb_checklist_guide(prev_step="pre", next_step="promo"),
        )

    @dp.callback_query(F.data == "checklists:promo")
    async def checklists_promo(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(
            CHECKLIST_PROMO,
            reply_markup=kb_checklist_guide(prev_step="post", next_step="safe_mode"),
        )

    @dp.callback_query(F.data == "checklists:safe_mode")
    async def checklists_safe_mode(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(
            CHECKLIST_SAFE_MODE,
            reply_markup=kb_checklist_guide(prev_step="promo", next_step=None),
        )

    @dp.callback_query(F.data == "main:strategies")
    async def strategies_main(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(STRATEGIES_MENU_TEXT, reply_markup=kb_strategies_menu())

    @dp.callback_query(F.data == "strategies:spot_grid")
    async def strategy_spot_grid(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(
            STRATEGY_SPOT_GRID_TEXT,
            reply_markup=kb_strategy_guide(prev_step=None, next_step="trailing"),
        )

    @dp.callback_query(F.data == "strategies:trailing")
    async def strategy_trailing(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(
            STRATEGY_TRAILING_TEXT,
            reply_markup=kb_strategy_guide(prev_step="spot_grid", next_step="swing"),
        )

    @dp.callback_query(F.data == "strategies:swing")
    async def strategy_swing(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(
            STRATEGY_SWING_TEXT,
            reply_markup=kb_strategy_guide(prev_step="trailing", next_step="manual_1m"),
        )

    @dp.callback_query(F.data == "strategies:manual_1m")
    async def strategy_manual_1m(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(
            STRATEGY_MANUAL_1M_TEXT,
            reply_markup=kb_strategy_guide(prev_step="swing", next_step=None),
        )

    @dp.callback_query(F.data == "main:private")
    async def private_join(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer("Готовлю ссылку...")
        ok, message = await issue_private_channel_invite(bot, cfg, cq.from_user.id)
        prefix = "✅ " if ok else "❌ "
        await cq.message.answer(prefix + message)


    @dp.message(Command("coins"))
    async def coins_search_take(m: Message):
        query = (m.text or "").split(maxsplit=1)
        raw_query = query[1].strip() if len(query) > 1 else ""
        await _handle_coins_search(m, raw_query)

    @dp.message(F.text & ~F.text.startswith("/"))
    async def coins_search_take_text(m: Message):
        await _handle_coins_search(m, (m.text or "").strip())

    async def _handle_coins_search(m: Message, raw_query: str):
        if not raw_query:
            return

        await db.upsert_user(cfg.db_path, m.from_user.id, m.from_user.username)
        symbols = coins.search_market_symbols(raw_query, limit=10)
        if not symbols:
            await m.answer(
                "Не нашёл подходящих рынков.\n"
                "Примеры запроса: BTC, rave, eth/usdt",
            )
            return

        if len(symbols) == 1:
            symbol = symbols[0]
            await db.set_active_symbol(cfg.db_path, m.from_user.id, symbol)
            await m.answer(
                f"Выбран символ: {hbold(symbol)}\nЧто сделать дальше?",
                reply_markup=_kb_symbol_actions(symbol),
            )
            return

        await m.answer(
            "Нашёл несколько совпадений. Выбери нужный символ:",
            reply_markup=_kb_symbol_choices(symbols),
        )

    @dp.callback_query(F.data.startswith("coins:set:"))
    async def coins_set_symbol(cq: CallbackQuery):
        parts = (cq.data or "").split(":", maxsplit=2)
        if len(parts) < 3:
            await cq.answer("Некорректный символ", show_alert=True)
            return
        symbol = parts[2]
        await db.upsert_user(cfg.db_path, cq.from_user.id, cq.from_user.username)
        await db.set_active_symbol(cfg.db_path, cq.from_user.id, symbol)
        await cq.answer("Символ выбран")
        await cq.message.answer(
            f"Активный символ: {hbold(symbol)}\nЧто сделать дальше?",
            reply_markup=_kb_symbol_actions(symbol),
        )

    @dp.callback_query(F.data.startswith("coins:fav:add:"))
    async def coins_add_favorite(cq: CallbackQuery):
        parts = (cq.data or "").split(":", maxsplit=3)
        if len(parts) < 4:
            await cq.answer("Некорректный символ", show_alert=True)
            return
        symbol = parts[3]
        await db.add_favorite(cfg.db_path, cq.from_user.id, symbol)
        await cq.answer("Добавлено в избранное ✅")

    @dp.callback_query(F.data.startswith("coins:chart:"))
    async def coins_chart(cq: CallbackQuery):
        parts = (cq.data or "").split(":", maxsplit=2)
        if len(parts) < 3:
            await cq.answer("Некорректный символ", show_alert=True)
            return
        symbol = parts[2]
        await cq.answer("Готовлю график...")
        try:
            df = charts.fetch_ohlcv(symbol, timeframe="15m", limit=220)
            df = charts.add_ma30(df)
            png = charts.render_png(df, f"{symbol} • 15m")
        except Exception:
            await cq.message.answer("Не удалось построить график. Попробуй позже.")
            return

        await cq.message.answer_photo(BufferedInputFile(png, filename="chart.png"), caption=f"📈 {symbol}")

    await dp.start_polling(bot)

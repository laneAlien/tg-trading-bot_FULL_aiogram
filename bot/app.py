import asyncio
import secrets
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from aiogram.utils.markdown import hbold, hcode

from . import db
from .config import load_config
from .keyboards import kb_access, kb_main
from .texts import DISCLAIMER


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
        except Exception as e:
            print(f"[reminder_loop] error={e}")
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
    return True, f"🔗 Ссылка для входа:\n{invite.invite_link}"


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

    asyncio.create_task(expiry_reminder_loop(bot, cfg))

    @dp.message(CommandStart())
    async def start(m: Message):
        await db.upsert_user(cfg.db_path, m.from_user.id, m.from_user.username)
        await maybe_send_expiry_notice(bot, cfg, m.from_user.id)
        await m.answer(
            "🏠 Бот упрощён: оставлен только доступ и вход в закрытый канал.\n"
            "Остальные функции переезжают в чат и будут дорабатываться.",
            reply_markup=kb_main(),
        )

    @dp.message(Command("getchatid"))
    async def getchatid(m: Message):
        await m.answer(f"chat_id = {hcode(str(m.chat.id))}")

    @dp.callback_query(F.data == "nav:back:main")
    async def back_main(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text("🏠 Главное меню", reply_markup=kb_main())

    @dp.callback_query(F.data == "main:help")
    async def help_(cq: CallbackQuery):
        await cq.answer()
        await cq.message.answer(
            "ℹ️ Сейчас в боте доступны только:\n"
            "• ⭐ управление доступом\n"
            "• 🔒 выдача ссылки в закрытый канал\n\n"
            "Остальные функции будут в отдельном чате после доработки.",
            reply_markup=kb_main(),
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
        await m.answer(
            "✅ Оплата получена. Доступ активен на 30 дней.\n"
            f"Подписка до: {hcode(until[:19])}",
            reply_markup=kb_main(),
        )

    @dp.callback_query(F.data == "main:private")
    async def private_join(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer("Готовлю ссылку...")
        ok, message = await issue_private_channel_invite(bot, cfg, cq.from_user.id)
        prefix = "✅ " if ok else "❌ "
        await cq.message.answer(prefix + message)

    await dp.start_polling(bot)

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.markdown import hbold, hcode

from datetime import datetime, timezone
import aiosqlite
import secrets

from .config import load_config
from . import db
from .keyboards import (
    kb_main,
    kb_access,
    kb_support,
    kb_ticket_admin,
    kb_admin_panel,
    kb_coins_menu,
    kb_chart_tf,
    kb_symbol_actions,
    kb_journal,
)
from .charts import fetch_ohlcv, add_ma30, detect_regime, render_png
from .coins import top_movers
from .texts import DECISION_BRIEF, PROMO_TEXT, TILT_TEXT, CHECKLIST_PRE, CHECKLIST_POST, DISCLAIMER


class SupportStates(StatesGroup):
    waiting_ticket_text = State()


class AdminStates(StatesGroup):
    waiting_reply_text = State()
    waiting_broadcast_text = State()
    waiting_whitelist_add = State()
    waiting_whitelist_remove = State()


class CoinsStates(StatesGroup):
    awaiting_symbol_search = State()


class JournalStates(StatesGroup):
    awaiting_journal_text = State()


async def ensure_access(cfg, cq: CallbackQuery) -> bool:
    ok = await db.is_access_active(cfg.db_path, cq.from_user.id)
    if ok:
        return True
    await cq.answer()
    await cq.message.answer("Доступ не активен. Открой ⭐ Доступ.", reply_markup=kb_access())
    return False


def mk_payload(user_id: int) -> str:
    return f"access30d:{user_id}:{int(datetime.now(timezone.utc).timestamp())}:{secrets.token_hex(4)}"


async def run():
    cfg = load_config()
    await db.init_db(cfg.db_path)

    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    me = await bot.get_me()
    print(
        f"[startup] bot_id={me.id} admin_user_id={cfg.admin_user_id} "
        f"support_group_id={cfg.support_group_id} private_channel_id={cfg.private_channel_id}"
    )
    if cfg.private_channel_id:
        try:
            private_chat = await bot.get_chat(int(cfg.private_channel_id))
            print(
                f"[startup] private_chat_ok id={private_chat.id} "
                f"type={private_chat.type} title={getattr(private_chat, 'title', None)}"
            )
        except Exception as e:
            print(f"[startup] private_chat_check_failed id={cfg.private_channel_id} error={e}")

    @dp.message(CommandStart())
    async def start(m: Message):
        await db.upsert_user(cfg.db_path, m.from_user.id, m.from_user.username)
        await m.answer("🏠 Главное меню\n\n⚠️ Не финсовет.", reply_markup=kb_main())

    @dp.message(Command("admin"))
    async def admin(m: Message):
        if m.from_user.id != cfg.admin_user_id:
            return
        await m.answer("🛠 Админ-панель", reply_markup=kb_admin_panel())

    @dp.message(Command("getchatid"))
    async def getchatid(m: Message):
        await m.answer(f"chat_id = {hcode(str(m.chat.id))}")

    @dp.message(Command("diag"))
    async def diag(m: Message):
        if m.from_user.id != cfg.admin_user_id:
            return
        private_id = int(cfg.private_channel_id) if cfg.private_channel_id else None
        lines = [
            f"bot_id={hcode(str((await bot.get_me()).id))}",
            f"support_group_id={hcode(str(cfg.support_group_id))}",
            f"private_channel_id={hcode(str(private_id))}",
        ]
        if private_id is not None:
            try:
                chat = await bot.get_chat(private_id)
                lines.append(
                    f"private_chat={hcode(str(chat.id))} type={hcode(str(chat.type))} title={hcode(str(getattr(chat, 'title', None)))}"
                )
            except Exception as e:
                lines.append(f"private_chat_error={hcode(str(e))}")
        await m.answer("\n".join(lines))

    @dp.callback_query(F.data == "nav:back:main")
    async def back_main(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text("🏠 Главное меню", reply_markup=kb_main())

    # ===== Access / Stars =====
    @dp.callback_query(F.data == "main:access")
    async def access_main(cq: CallbackQuery):
        await db.upsert_user(cfg.db_path, cq.from_user.id, cq.from_user.username)
        await cq.answer()
        await cq.message.edit_text("⭐ Доступ", reply_markup=kb_access())

    @dp.callback_query(F.data == "access:disclaimer")
    async def disclaimer(cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(DISCLAIMER + "\n\nНажми ✅ Я согласен.", reply_markup=kb_access())

    @dp.callback_query(F.data == "access:disclaimer:agree")
    async def disclaimer_agree(cq: CallbackQuery):
        await cq.answer("Ок")
        await db.set_disclaimer(cfg.db_path, cq.from_user.id)
        await cq.message.edit_text("✅ Согласие сохранено. Теперь можно купить доступ.", reply_markup=kb_access())

    @dp.callback_query(F.data == "access:status")
    async def access_status(cq: CallbackQuery):
        await cq.answer()
        u = await db.get_user(cfg.db_path, cq.from_user.id) or {}
        active = await db.is_access_active(cfg.db_path, cq.from_user.id)
        txt = f"Статус: {hbold('АКТИВЕН' if active else 'НЕ АКТИВЕН')}\n"
        if u.get("is_whitelisted") == 1:
            txt += "Режим: FREE (whitelist)\n"
        else:
            txt += f"access_until: {hcode(str(u.get('access_until')))}\n"
        txt += f"active_symbol: {hcode(str(u.get('active_symbol')))}"
        await cq.message.edit_text(txt, reply_markup=kb_access())

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
        expected = int(p["stars_amount"])
        if int(sp.total_amount) != expected:
            await bot.send_message(
                cfg.support_group_id,
                f"⚠️ Payment amount mismatch payload={payload} got={sp.total_amount} expected={expected}",
            )
            return
        await db.mark_payment_paid(cfg.db_path, payload)
        await db.grant_access_30d(cfg.db_path, m.from_user.id)
        await m.answer("✅ Оплата получена. Доступ активен на 30 дней.", reply_markup=kb_main())

    # Help
    @dp.callback_query(F.data == "main:help")
    async def help_(cq: CallbackQuery):
        await cq.answer()
        await cq.message.answer("ℹ️ Помощь\n\n— /getchatid\n— /admin (админ)\n\n⚠️ Не финсовет.", reply_markup=kb_main())

    # Coins
    @dp.callback_query(F.data == "main:coins")
    async def coins(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        await cq.message.edit_text("🪙 Монеты", reply_markup=kb_coins_menu())

    @dp.callback_query(F.data.in_({"coins:gainers", "coins:losers"}))
    async def coins_movers(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer("Считаю...")
        direction = "gainers" if cq.data.endswith("gainers") else "losers"
        movers = top_movers(limit=10, direction=direction)
        lines = [f"{i+1}) <code>{sym}</code>  {pct:+.2f}%" for i, (sym, pct) in enumerate(movers)]
        await cq.message.answer(
            ("📈 Топ рост\n" if direction == "gainers" else "📉 Топ падение\n")
            + "\n".join(lines)
            + "\n\n🔎 Поиск → выбрать монету"
        )

    @dp.callback_query(F.data == "coins:favorites")
    async def coins_favorites(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        favs = await db.list_favorites(cfg.db_path, cq.from_user.id, 30)
        if not favs:
            return await cq.message.answer("⭐ Избранное пустое. Добавь через 🔎 Поиск.")
        msg = "⭐ Избранное:\n" + "\n".join([f"• <code>{s}</code>" for s in favs])
        await cq.message.answer(msg)

    @dp.callback_query(F.data == "coins:search")
    async def coins_search(cq: CallbackQuery, state: FSMContext):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        await state.set_state(CoinsStates.awaiting_symbol_search)
        await cq.message.answer("Введи символ в формате <code>RAVE/USDT</code>")

    @dp.message(CoinsStates.awaiting_symbol_search, F.text)
    async def coins_search_take(m: Message, state: FSMContext):
        symbol = m.text.strip().upper().replace("_", "/")
        await state.clear()
        await db.upsert_user(cfg.db_path, m.from_user.id, m.from_user.username)
        await db.set_active_symbol(cfg.db_path, m.from_user.id, symbol)
        favs = await db.list_favorites(cfg.db_path, m.from_user.id, 200)
        is_fav = symbol in favs
        await m.answer(f"✅ Активная монета: <code>{symbol}</code>", reply_markup=kb_symbol_actions(symbol, is_fav))

    @dp.callback_query(F.data.startswith("coins:set:"))
    async def coins_set(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        symbol = cq.data.split(":", 2)[2]
        await cq.answer("OK")
        await db.set_active_symbol(cfg.db_path, cq.from_user.id, symbol)
        favs = await db.list_favorites(cfg.db_path, cq.from_user.id, 200)
        await cq.message.answer(
            f"✅ Активная монета: <code>{symbol}</code>",
            reply_markup=kb_symbol_actions(symbol, symbol in favs),
        )

    @dp.callback_query(F.data.startswith("coins:fav:"))
    async def coins_fav(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        _, _, action, symbol = cq.data.split(":", 3)
        await cq.answer()
        if action == "add":
            await db.add_favorite(cfg.db_path, cq.from_user.id, symbol)
            await cq.message.answer("⭐ Добавлено в избранное")
        else:
            await db.remove_favorite(cfg.db_path, cq.from_user.id, symbol)
            await cq.message.answer("🗑 Удалено из избранного")

    # Regime/Charts
    @dp.callback_query(F.data == "main:regime")
    async def regime(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        await cq.message.edit_text("📊 Выбери TF", reply_markup=kb_chart_tf())

    @dp.callback_query(F.data.startswith("chart:tf:"))
    async def chart(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        tf = cq.data.split(":")[-1]
        await cq.answer("График...")
        u = await db.get_user(cfg.db_path, cq.from_user.id) or {}
        symbol = u.get("active_symbol") or "RAVE/USDT"
        try:
            df = add_ma30(fetch_ohlcv(symbol, tf))
            reg = detect_regime(df)
            png = render_png(df, f"{symbol} • {tf} • MA30 • {reg}")
        except Exception as e:
            return await cq.message.answer(f"❌ Ошибка: <code>{str(e)[:200]}</code>")
        await cq.message.answer_photo(
            photo=png,
            caption=f"{hbold(symbol)} • {hcode(tf)}\nРежим: {hbold(reg)}\n\n{DECISION_BRIEF}",
            reply_markup=kb_chart_tf(),
        )

    # Guides
    @dp.callback_query(F.data == "main:promo")
    async def promo(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        await cq.message.answer(PROMO_TEXT)

    @dp.callback_query(F.data == "main:tilt")
    async def tilt(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        await cq.message.answer(TILT_TEXT)

    @dp.callback_query(F.data == "main:checklists")
    async def checklists(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        await cq.message.answer(CHECKLIST_PRE + "\n\n" + CHECKLIST_POST)

    @dp.callback_query(F.data == "main:strategies")
    async def strategies(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        await cq.message.answer("⚙️ Стратегии\n\n" + DECISION_BRIEF)

    # Journal
    @dp.callback_query(F.data == "main:journal")
    async def journal(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        await cq.message.edit_text("🧾 Журнал", reply_markup=kb_journal())

    @dp.callback_query(F.data == "journal:add")
    async def journal_add(cq: CallbackQuery, state: FSMContext):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        await state.set_state(JournalStates.awaiting_journal_text)
        await cq.message.answer("Напиши запись (1 сообщение).")

    @dp.message(JournalStates.awaiting_journal_text, F.text)
    async def journal_take(m: Message, state: FSMContext):
        await state.clear()
        await db.add_journal(cfg.db_path, m.from_user.id, m.text.strip())
        await m.answer("✅ Запись добавлена", reply_markup=kb_main())

    @dp.callback_query(F.data == "journal:list")
    async def journal_list(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        items = await db.list_journal(cfg.db_path, cq.from_user.id, 20)
        if not items:
            return await cq.message.answer("Пусто")
        txt = "🗂 Последние записи:\n\n" + "\n\n".join([f"{hcode(ts[:19])}\n{t}" for ts, t in items])
        await cq.message.answer(txt)

    # Privatka
    @dp.callback_query(F.data == "main:privatka")
    async def privatka(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        if not cfg.private_channel_id:
            return await cq.message.answer("PRIVATE_CHANNEL_ID не задан в .env")

        channel_id = int(cfg.private_channel_id)
        try:
            chat = await bot.get_chat(channel_id)
            # member_limit supported for supergroup, but not for channel chats
            if chat.type == "supergroup":
                link = await bot.create_chat_invite_link(chat_id=channel_id, member_limit=1)
                await cq.message.answer(f"🔒 Приватка — одноразовая ссылка:\n{link.invite_link}")
            else:
                link = await bot.create_chat_invite_link(chat_id=channel_id)
                await cq.message.answer(
                    "🔒 Приватка — ссылка в канал (для каналов Telegram не поддерживает one-time member_limit):"
                    f"\n{link.invite_link}"
                )
        except Exception as e:
            await cq.message.answer(
                "❌ Не смог создать invite-link. "
                f"chat_id=<code>{channel_id}</code>\n"
                f"<code>{str(e)[:300]}</code>"
            )
    # Support
    @dp.callback_query(F.data == "main:support")
    async def support(cq: CallbackQuery):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        await cq.message.edit_text("🆘 Поддержка", reply_markup=kb_support())

    @dp.callback_query(F.data == "support:new")
    async def support_new(cq: CallbackQuery, state: FSMContext):
        if not await ensure_access(cfg, cq):
            return
        await cq.answer()
        await state.set_state(SupportStates.waiting_ticket_text)
        await cq.message.answer("Опиши проблему одним сообщением.")

    @dp.message(SupportStates.waiting_ticket_text, F.text)
    async def support_take(m: Message, state: FSMContext):
        await state.clear()
        await db.upsert_user(cfg.db_path, m.from_user.id, m.from_user.username)
        ticket_id = await db.create_ticket(cfg.db_path, m.from_user.id, m.text or "")
        await m.answer(f"✅ Тикет <code>#{ticket_id}</code> создан. Мы ответим здесь.")
        txt = (
            f"🆘 <b>Тикет</b> <code>#{ticket_id}</code>\n"
            f"user_id: <code>{m.from_user.id}</code>\n"
            f"username: @{m.from_user.username if m.from_user.username else '—'}\n\n"
            f"{m.text or ''}"
        )
        try:
            await bot.send_message(cfg.support_group_id, txt, reply_markup=kb_ticket_admin(ticket_id))
        except Exception:
            pass

    # Admin ticket actions from support group
    @dp.callback_query(F.data.startswith("admin:tickets:reply:"))
    async def admin_reply_btn(cq: CallbackQuery, state: FSMContext):
        if cq.from_user.id != cfg.admin_user_id:
            return await cq.answer("Not allowed")
        ticket_id = int(cq.data.split(":")[-1])
        await state.set_state(AdminStates.waiting_reply_text)
        await state.update_data(ticket_id=ticket_id)
        await cq.answer()
        await cq.message.reply(f"✍️ Напиши ответ для <code>#{ticket_id}</code> одним сообщением.")

    @dp.message(AdminStates.waiting_reply_text, F.text)
    async def admin_reply_text(m: Message, state: FSMContext):
        if m.from_user.id != cfg.admin_user_id:
            return
        data = await state.get_data()
        ticket_id = int(data.get("ticket_id"))
        await state.clear()

        async with aiosqlite.connect(cfg.db_path) as dbs:
            dbs.row_factory = aiosqlite.Row
            cur = await dbs.execute("SELECT user_id FROM tickets WHERE ticket_id=?", (ticket_id,))
            row = await cur.fetchone()
        if not row:
            return await m.reply("❌ Тикет не найден")
        user_id = int(row["user_id"])
        await db.add_ticket_message(cfg.db_path, ticket_id, "admin", m.text)
        await bot.send_message(user_id, f"💬 Ответ по тикету <code>#{ticket_id}</code>:\n\n{m.text}")
        await m.reply("✅ Отправлено")

    @dp.callback_query(F.data.startswith("admin:tickets:close:"))
    async def admin_close_btn(cq: CallbackQuery):
        if cq.from_user.id != cfg.admin_user_id:
            return await cq.answer("Not allowed")
        ticket_id = int(cq.data.split(":")[-1])
        await db.close_ticket(cfg.db_path, ticket_id)
        await cq.answer("Закрыто")
        await cq.message.reply(f"✅ Тикет <code>#{ticket_id}</code> закрыт")

    # Admin panel (private chat)
    @dp.callback_query(F.data == "admin:tickets:open")
    async def admin_open(cq: CallbackQuery):
        if cq.from_user.id != cfg.admin_user_id:
            return await cq.answer("Not allowed")
        await cq.answer()
        tickets = await db.get_open_tickets(cfg.db_path, 20)
        if not tickets:
            return await cq.message.answer("Открытых тикетов нет")
        for t in tickets:
            await cq.message.answer(
                f"🆘 <code>#{t['ticket_id']}</code> user_id=<code>{t['user_id']}</code>",
                reply_markup=kb_ticket_admin(int(t["ticket_id"])),
            )

    @dp.callback_query(F.data == "admin:broadcast:new")
    async def admin_broadcast_new(cq: CallbackQuery, state: FSMContext):
        if cq.from_user.id != cfg.admin_user_id:
            return await cq.answer("Not allowed")
        await cq.answer()
        await state.set_state(AdminStates.waiting_broadcast_text)
        await cq.message.answer("📣 Текст рассылки одним сообщением:")

    @dp.message(AdminStates.waiting_broadcast_text, F.text)
    async def admin_broadcast_send(m: Message, state: FSMContext):
        if m.from_user.id != cfg.admin_user_id:
            return
        await state.clear()
        async with aiosqlite.connect(cfg.db_path) as dbs:
            dbs.row_factory = aiosqlite.Row
            cur = await dbs.execute("SELECT user_id, is_whitelisted, access_until FROM users")
            rows = await cur.fetchall()
        sent = 0
        for r in rows:
            uid = int(r["user_id"])
            active = r["is_whitelisted"] == 1
            if not active and r["access_until"]:
                try:
                    dt = datetime.fromisoformat(r["access_until"].replace("Z", "+00:00"))
                    active = dt > datetime.now(timezone.utc)
                except Exception:
                    active = False
            if not active:
                continue
            try:
                await bot.send_message(uid, f"📣 {m.text}")
                sent += 1
            except Exception:
                pass
        await m.reply(f"✅ Разослано: {sent}")

    @dp.callback_query(F.data == "admin:whitelist:add")
    async def wl_add(cq: CallbackQuery, state: FSMContext):
        if cq.from_user.id != cfg.admin_user_id:
            return await cq.answer("Not allowed")
        await cq.answer()
        await state.set_state(AdminStates.waiting_whitelist_add)
        await cq.message.answer("user_id для whitelist ADD:")

    @dp.message(AdminStates.waiting_whitelist_add, F.text)
    async def wl_add_do(m: Message, state: FSMContext):
        if m.from_user.id != cfg.admin_user_id:
            return
        await state.clear()
        uid = int(m.text.strip())
        await db.upsert_user(cfg.db_path, uid, None)
        await db.set_whitelist(cfg.db_path, uid, True)
        await m.reply("✅ Добавлен")

    @dp.callback_query(F.data == "admin:whitelist:remove")
    async def wl_remove(cq: CallbackQuery, state: FSMContext):
        if cq.from_user.id != cfg.admin_user_id:
            return await cq.answer("Not allowed")
        await cq.answer()
        await state.set_state(AdminStates.waiting_whitelist_remove)
        await cq.message.answer("user_id для whitelist REMOVE:")

    @dp.message(AdminStates.waiting_whitelist_remove, F.text)
    async def wl_remove_do(m: Message, state: FSMContext):
        if m.from_user.id != cfg.admin_user_id:
            return
        await state.clear()
        uid = int(m.text.strip())
        await db.upsert_user(cfg.db_path, uid, None)
        await db.set_whitelist(cfg.db_path, uid, False)
        await m.reply("✅ Убран")

    await dp.start_polling(bot)

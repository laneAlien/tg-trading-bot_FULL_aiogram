# TG Trading Bot (aiogram) — FULL (self-host)
Included:
- Disclaimer + whitelist FREE + Telegram Stars paid access (30 days)
- Support tickets to a group + admin replies from that group
- Privatka: single-use invite links (bot must be admin in the channel)
- Coins: search, favorites, top gainers/losers (Gate via ccxt)
- Charts: 1m/5m/15m/30m chart + MA30 + simple regime detection
- Built-in guides: Decision/Promo/Tilt/Checklists
- Journal: add note + list recent

## Run
1) `cp .env.example .env` and fill values
2) `docker compose up -d --build`
3) In support group send `/getchatid` to get SUPPORT_GROUP_ID.

## Stars notes
- Currency must be `XTR` and provider_token must be omitted for Stars payments. citeturn0search4turn0search0
- We use `createInvoiceLink()` and handle `pre_checkout_query` + `successful_payment`. citeturn0search1turn0search2

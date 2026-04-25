# Ревью репозитория `laneAlien/tg-trading-bot_FULL_aiogram`

> Telegram-бот на aiogram для управления доступом и монетизацией с функциями трейдинга. Деплоится через Docker Compose.

---

## 1. Сводка приоритетов

| Приоритет | Что | Где |
|---|---|---|
| 🔴 High | `asyncio.create_task()` вызывается до запуска event loop — падение при старте | `app.py:run()` |
| 🔴 High | `expiry_reminder_loop` поглощает все исключения без логирования типа ошибки | `app.py:expiry_reminder_loop()` |
| 🔴 High | Файл базы данных `/data/bot.sqlite3` не исключён из git, путь в конфиге — абсолютный | `config.py:db_path` |
| 🟠 Med | Все обработчики определены внутри функции `run()` — невозможно протестировать отдельно | `app.py:run()` |
| 🟠 Med | Нет проверки на принятие дисклеймера при обработке `access:buy:30d` в случае повторной покупки | `app.py:access_buy()` |
| 🟠 Med | Блок `try/except Exception` в `maybe_send_expiry_notice` скрывает ошибки Telegram API | `app.py:maybe_send_expiry_notice()` |
| 🟠 Med | `market_data.py` создаёт новый объект exchange при каждом вызове `_retry_call` — нет переиспользования соединений | `market_data.py:_retry_call()` |
| 🟠 Med | Отсутствует README с описанием переменных окружения и инструкцией по запуску | корень проекта |
| 🟡 Low | `mk_payload` генерирует payload с временной меткой, но не проверяет TTL при обработке платежа | `app.py:successful_payment()` |
| 🟡 Low | `pyproject.toml` отсутствует — нет явной спецификации версий Python и зависимостей | корень проекта |
| 🟡 Low | В `.env.example` перечислены не все переменные (нет `STARS_PRICE`, `STARS_TITLE`, `STARS_DESCRIPTION`) | `.env.example` |
| 🟡 Low | `docker-compose.yml` не монтирует `/data` как volume — данные теряются при перезапуске контейнера | `docker-compose.yml` |

---

## 2. Критические проблемы

### 2.1 `asyncio.create_task()` до старта event loop

**Файл:** `app.py`, функция `run()`

```python
async def run() -> None:
    ...
    asyncio.create_task(expiry_reminder_loop(bot, cfg))  # ← проблема
    ...
    await dp.start_polling(bot)
```

`create_task` внутри `async def` корректен, но задача создаётся до того, как polling запущен. Если до `start_polling` выбрасывается исключение — задача утечёт без отмены. Правильный подход — запускать через `asyncio.gather` или через `on_startup` хук диспетчера:

```python
async def on_startup(bot: Bot):
    asyncio.create_task(expiry_reminder_loop(bot, cfg))

dp.startup.register(on_startup)
```

### 2.2 Поглощение исключений в reminder loop

**Файл:** `app.py`, функция `expiry_reminder_loop()`

```python
except Exception as e:
    print(f"[reminder_loop] error={e}")
```

Используется `print` вместо `logger.exception()`. При этом трассировка стека теряется. Заменить на:

```python
except Exception:
    logger.exception("[reminder_loop] Unexpected error")
```

### 2.3 SQLite путь и отсутствие volume в Docker

**Файл:** `config.py`, `docker-compose.yml`

Путь по умолчанию `/data/bot.sqlite3` — абсолютный. В `docker-compose.yml` отсутствует монтирование тома:

```yaml
# Нужно добавить:
volumes:
  - ./data:/data
```

Без этого при `docker compose down` данные пользователей теряются.

---

## 3. Серьёзные замечания

### 3.1 Определение хендлеров внутри `run()`

Все `@dp.message()` и `@dp.callback_query()` декораторы определены внутри `async def run()`. Это стандартная антипаттерн в aiogram: функции нельзя протестировать изолированно, нет возможности вынести роутеры в отдельные файлы. Рекомендуется вынести в отдельные Router-модули (aiogram 3.x поддерживает `Router`).

### 3.2 Нет README с environment variables

Отсутствует документация по обязательным переменным окружения. В `.env.example` есть только `BOT_TOKEN`, `ADMIN_USER_ID`, `SUPPORT_GROUP_ID` и `PRIVATE_CHANNEL_ID`. Не документированы: `STARS_PRICE`, `STARS_TITLE`, `STARS_DESCRIPTION`, `ANALYTICS_CHAT_URL`, `DB_PATH`, `TZ`.

### 3.3 Переиспользование exchange-объекта в market_data

```python
def get_exchange(exchange_id: str = PRIMARY_EXCHANGE) -> ccxt.Exchange:
    exchange_cls = getattr(ccxt, exchange_id)
    return exchange_cls(COMMON_EXCHANGE_PARAMS)  # новый объект каждый раз
```

При каждом вызове `_retry_call` создаётся новый объект exchange без сессии. Для rate-limiting это проблема: ccxt отслеживает лимиты на уровне объекта. Лучше хранить singleton:

```python
_exchanges: dict[str, ccxt.Exchange] = {}

def get_exchange(exchange_id: str = PRIMARY_EXCHANGE) -> ccxt.Exchange:
    if exchange_id not in _exchanges:
        _exchanges[exchange_id] = getattr(ccxt, exchange_id)(COMMON_EXCHANGE_PARAMS)
    return _exchanges[exchange_id]
```

---

## 4. Качество кода

### 4.1 Payload не имеет TTL-валидации

`mk_payload` кодирует timestamp:
```python
def mk_payload(user_id: int) -> str:
    ts = int(datetime.now(timezone.utc).timestamp())
    return f"access30d:{user_id}:{ts}:{secrets.token_hex(4)}"
```

Но в `successful_payment` timestamp не проверяется. Теоретически старый payload может быть переиспользован. Добавить проверку: если `ts` старше 24 часов — отклонять платёж.

### 4.2 `pyproject.toml` отсутствует

Проект использует `requirements.txt`, но нет явной версии Python. Добавить `pyproject.toml` с:
```toml
[tool.poetry]
python = ">=3.11"
```
Или зафиксировать Python-версию в `Dockerfile` (`FROM python:3.11-slim`).

### 4.3 Отсутствует `.gitignore` для данных

```
# Добавить в .gitignore:
data/
*.sqlite3
.env
```

---

## 5. Положительные стороны

- Архитектурно чистая реализация конфига через frozen dataclass — хорошая практика
- `db.py` использует параметризованные запросы — нет SQL-инъекций
- WAL-режим SQLite включён корректно
- Retry-логика в `market_data.py` с failover между биржами — правильный подход
- Dockerfile грамотно структурирован (отдельный слой для зависимостей)

---

## 6. Чек-лист правок

- [ ] Перенести `create_task` в `on_startup` диспетчера
- [ ] Заменить `print(...)` на `logger.exception(...)` в reminder loop
- [ ] Добавить volume `/data` в `docker-compose.yml`
- [ ] Создать полноценный `README.md` с описанием всех env-переменных
- [ ] Добавить `.env` и `data/` в `.gitignore`
- [ ] Добавить TTL-проверку payload в `successful_payment`
- [ ] Добавить singleton для exchange-объектов
- [ ] Вынести хендлеры в отдельные Router-модули

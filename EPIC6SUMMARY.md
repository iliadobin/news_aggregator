# Эпик 6: Юзер-бот (Telethon) — чтение сообщений из источников

Дата: 2025‑12‑17

## Что сделано

- Добавлен **юзер-бот на Telethon** (не Bot API), который читает новые сообщения из Telegram.
- Реализована **авторизация с session-файлом** (сохраняется на диск; повторный логин не нужен).
- Добавлены **handlers** для приёма новых сообщений (`events.NewMessage`) и передачи их в `Dispatcher`.
- Реализован **маппинг Telegram-сообщения → `IncomingMessage`** (`app/routing/dispatcher.py`) с:
  - `telegram_message_id`, `chat_id`, `date`, `text`
  - `metadata` (минимально полезные поля: sender_id, reply_to, media и т.п.)
  - `source_*` подсказки: `source_type`, `source_title`, `source_username`
- Подключено **сохранение минимального Source** через уже существующую логику `Dispatcher`:
  - если источника нет в БД — `Dispatcher` делает `get_or_create` `Source` по `telegram_chat_id`
  - затем сохраняет `Message` и запускает фильтрацию (как в эпике 5)
- Добавлено **устойчивое логирование ошибок**: исключения в хендлере не валят процесс, пишутся traceback’и.

## Как выбираются источники

- Юзер-бот принимает **только сообщения из источников, которые есть в БД** как активные `Source` (`is_active = true`).
- Список источников обновляется **периодически** через `SourceCache` (polling в фоне; по умолчанию раз в 60 секунд).

## Новые файлы

- `app/bots/user_bot/client.py` — создание `TelegramClient` с session-based auth.
- `app/bots/user_bot/handlers.py` — обработчики событий Telethon + `SourceCache` + маппинг в `IncomingMessage`.
- `app/bots/user_bot/runner.py` — запуск клиента, регистрация handlers, фоновое обновление источников.
- `app/bots/user_bot/__init__.py` — экспорт `run_userbot`.

## Конфигурация (env)

Используется `TelegramUserBotSettings` (`USERBOT_` префикс):

- `USERBOT_API_ID` — Telegram API ID
- `USERBOT_API_HASH` — Telegram API Hash
- `USERBOT_PHONE` — телефон аккаунта (нужен на первом запуске, чтобы создать/авторизовать сессию)
- `USERBOT_SESSION_NAME` — имя сессии (default: `news_aggregator_userbot`)
- `USERBOT_SESSION_DIR` — директория для session-файлов (default: `sessions`)

## Запуск

```bash
python -m app.bots.user_bot.runner
```

Примечания:
- при первом запуске Telethon может запросить код подтверждения (SMS/Telegram)
- если `USERBOT_PHONE` не задан, а сессия ещё не авторизована — запуск не пройдёт (это будет видно в логах)

## Ограничения текущей версии

- Forwarding в Telegram пока **не подключён** (в `Dispatcher` передаётся `forwarder=None`), то есть юзер-бот сейчас делает ingestion → dispatch → запись в БД/матчи/forward-tasks, но реальную пересылку будет логичнее подключить отдельно (в эпике control-bot/forwarder).


# Deployment contract

## PWA acceptance

`/sw.js` обслуживает root scope; reverse proxy должен отдавать этот путь без redirect
и не заменять JavaScript HTML-страницей. Settings/Data показывает установку только после
сигнала браузера о готовности. Chrome eligibility проверена локально; фактическая установка
и standalone launch на production HTTPS остаются ручной проверкой. Кэшируется только
public shell, не приватные API, admin, баланс или учебные данные. Offline shell не означает
полную работу расписания/AI без сети. Старый worker `/static/` снимается выборочно.

Student OS готов к staging-развёртыванию как один ASGI web process, но этот checkpoint ничего не публикует и не создаёт платные ресурсы.

## Обязательная production-конфигурация

- `APP_ENV=production`, `DEV_LOGIN_ENABLED=false` и `DEV_ADMIN_ENABLED=false` — development-вход и bootstrap администратора закрыты, session cookie получает `Secure`. Даже ошибочно включённый `DEV_ADMIN_ENABLED` игнорируется вне development.
- `DATABASE_PATH` должен указывать на постоянный подключённый volume. Эфемерная SQLite удалит пользователей и их данные при пересоздании инстанса.
- HTTPS завершается на доверенном reverse proxy, который не логирует cookie, Telegram payload или тела пользовательских запросов.
- `TELEGRAM_BOT_TOKEN`, разрешённый домен/redirect, `OWNER_TELEGRAM_ID` и `BOT_BRIDGE_SECRET` задаются только через secret storage платформы.
- `OPENAI_API_KEY` необязателен для деморежима; production-ключ хранится только в secret storage.
- `TELEGRAM_CLIENT_ID`, `TELEGRAM_CLIENT_SECRET`, `TELEGRAM_REDIRECT_URI` включают OIDC UI; callback должен быть HTTPS `/api/auth/telegram/callback` и зарегистрирован в BotFather. RS256 — единственный разрешённый алгоритм текущей реализации.
- Reverse proxy не должен логировать query string callback (authorization code). Штатный Uvicorn access log отключён; callback отдаёт `no-store` и `no-referrer`.

`ENTITLEMENT_SOURCE=core` включает новый authoritative Student OS ledger. `unconnected` — аварийный fail-closed режим, в котором AI и credit mutations отклоняются. `BOT_BRIDGE_SECRET` должен быть длинным случайным значением, одинаковым только у Core и Telegram adapter; bridge без него возвращает 503.

Если настроен `TELEGRAM_BOT_USERNAME`, Web показывает deep link `https://t.me/<bot>?start=buy`. Секрет bridge, подписи, Telegram payload и task bodies нельзя писать в proxy/application logs.

## Процесс и проверка

`Procfile` запускает один ASGI web process через порт платформы. Перед переводом трафика нужно применить конфигурацию, запустить приложение на persistent volume и проверить `GET /api/health`: ожидается `{"status":"ok","stage":"BETA_FOUNDATION"}`.

Публичный rollout заблокирован до настройки Telegram production login/domain и проверки постоянного хранилища. Автоматический deploy и покупка ресурсов намеренно не добавлены.

## Данные и восстановление

Пользователь может скачать versioned JSON со своими настройками, занятиями и дедлайнами. Сессии, CSRF, Telegram identity, feedback и admin-аудит в него не входят.

Restore реализован: upload → validation → preview → explicit replace confirmation → atomic transaction. Лимиты 5 МБ/10 000 записей, schema_version=1. Сначала сохраните текущий экспорт. Preview привязан к user, файлу и текущему состоянию, действует пять минут. user_id/private поля и пересечения отклоняются; IDs создаются заново. Баланс, Telegram, sessions, платежи и аудит не затрагиваются.

## Staging и ручной cutover

1. Backup legacy bot DB, Core DB и outbox; не подменять один другим.
2. Совместимые версии Core/bot на HTTPS с persistent volumes; bridge OFF.
3. OIDC Allowed URLs/RS256 и secrets вне Git; проверить owner `8247777174` и обычного пользователя.
4. Synthetic signed health/catalog/identity/AI/payment/outage smoke. GET /api/health — liveness; signed POST /api/internal/v1/health — ledger-ready, AI mode, pending reservations.
5. Export/restore на disposable staging account, mobile UI, реальные OCR-примеры. Платные AI/Stars — только после отдельного разрешения.
6. Владелец включает flag и перезапускает managed bot. Проверить /balance, /buy, text, photo, Web refresh, admin.
7. Rollback: flag OFF + ручной restart. Pending outbox сохранить и доставить/сверить; не терять оплаченные Stars.

Зависшие reserved после аварии процесса не возвращаются автоматически: оператор сверяет
запрос и выдаёт аудируемую компенсацию через admin; lease/recovery policy — следующий hardening.
Proxy ограничивает request size/time, не логирует auth callback query/cookies. Один SQLite
writer/process — текущая staging topology. Production deploy автоматически не выполнялся.

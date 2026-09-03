# Deployment contract

Student OS готов к staging-развёртыванию как один ASGI web process, но этот checkpoint ничего не публикует и не создаёт платные ресурсы.

## Обязательная production-конфигурация

- `APP_ENV=production`, `DEV_LOGIN_ENABLED=false` и `DEV_ADMIN_ENABLED=false` — development-вход и bootstrap администратора закрыты, session cookie получает `Secure`. Даже ошибочно включённый `DEV_ADMIN_ENABLED` игнорируется вне development.
- `DATABASE_PATH` должен указывать на постоянный подключённый volume. Эфемерная SQLite удалит пользователей и их данные при пересоздании инстанса.
- HTTPS завершается на доверенном reverse proxy, который не логирует cookie, Telegram payload или тела пользовательских запросов.
- `TELEGRAM_BOT_TOKEN`, разрешённый домен/redirect и `ADMIN_TELEGRAM_ID` задаются только через secret storage платформы.
- `OPENAI_API_KEY` необязателен для деморежима; production-ключ хранится только в secret storage.

`ENTITLEMENT_SOURCE=unconnected` остаётся безопасным значением до подключения авторитетного ledger adapter. Ручные credit mutations при этом отклоняются. `local` допустим только для изолированного staging.

## Процесс и проверка

`Procfile` запускает один ASGI web process через порт платформы. Перед переводом трафика нужно применить конфигурацию, запустить приложение на persistent volume и проверить `GET /api/health`: ожидается `{"status":"ok","stage":"BETA_FOUNDATION"}`.

Публичный rollout заблокирован до настройки Telegram production login/domain и проверки постоянного хранилища. Автоматический deploy и покупка ресурсов намеренно не добавлены.

## Данные и восстановление

Пользователь может скачать versioned JSON со своими настройками, занятиями и дедлайнами. Сессии, CSRF, Telegram identity, feedback и admin-аудит в него не входят.

Restore пока отсутствует. Безопасный будущий flow: upload → schema validation → owned-data preview → explicit replace confirmation → одна атомарная транзакция. Сервер не должен принимать `user_id` из файла или частично применять повреждённый архив.

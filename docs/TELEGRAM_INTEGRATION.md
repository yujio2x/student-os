# Telegram login, credits и cloud backup

Статус: internal identity, server sessions, Telegram HMAC verification и account-link boundary реализованы; live production UI/configuration ещё заблокированы credentials/domain.

## Фактическая реализация

- `users.id` — внутренний UUID Student OS. Telegram ID хранится только в `external_identities`.
- Legacy Login Widget payload проверяется на сервере по официальному HMAC-SHA-256 контракту, включая `auth_date`; payload разрешено использовать один раз.
- Новый подтверждённый Telegram ID атомарно создаёт internal user, существующий возвращает того же user. Конфликт одной Telegram identity между пользователями отклоняется.
- Удаление единственного production login заблокировано до появления безопасного recovery method.
- Bot token остаётся только в environment. При его отсутствии API честно возвращает `503`, а UI показывает setup state.
- Telegram в 2026 году также предлагает новый [OIDC flow с Authorization Code и PKCE](https://core.telegram.org/bots/telegram-login). Это предпочтительный live UI после получения Client ID/Secret и регистрации redirect URL; текущий HMAC boundary остаётся проверяемым совместимым вариантом для существующего bot token.

## Product boundaries

- Telegram login связывает существующего пользователя `student-ai-bot` с аккаунтом Student OS.
- Credits ограничивают только Student AI.
- Schedule, Calendar, Deadlines, настройки и базовые организационные функции не зависят от баланса credits.
- Telegram остаётся adapter/bridge, но не становится владельцем Student OS Core.

## Целевая модель идентичности

Student OS должен иметь собственный стабильный `user_id`. Telegram ID хранится как внешняя привязка, а не как primary key всей системы.

```text
Student OS user
├── profile / settings
├── schedule / deadlines / calendar
├── Telegram account link
│   └── telegram_user_id
└── Student AI entitlement
    └── credits ledger bridge
```

Owned-таблицы используют internal `user_id` из проверенной server-side session. `local-demo-user` остался только как маркер одноразовой миграции старой локальной базы.

## Login flow

1. Пользователь запускает вход через официальный Telegram login flow.
2. Backend проверяет подпись Telegram, свежесть `auth_date` и допустимый origin.
3. Backend создаёт или находит Student OS user и сохраняет связь с `telegram_user_id`.
4. Браузер получает серверную session cookie с `HttpOnly`, `Secure` и подходящим `SameSite`.
5. Клиент никогда не выбирает `user_id` самостоятельно и не считается источником истины для Telegram identity.

Нельзя принимать Telegram ID или баланс credits из непроверенного browser payload. Bot token, OpenAI key и session secrets хранятся только в environment/secrets storage.

## Unified credits integration

Рекомендуемая граница — отдельный `StudentAIEntitlementService` в application layer:

- `get_balance(user_id)`;
- `reserve_credit(user_id, request_id)`;
- `commit_usage(request_id)`;
- `release_reservation(request_id)`.

Student OS Core — новый source of truth для trial, credits, unlimited, reservations, token totals и Telegram Stars payments. Старый bot SQLite остаётся archive/rollback reference и не мигрируется автоматически.

Telegram adapter вызывает узкий `/api/internal/v1/*` API с HMAC-SHA-256 подписью timestamp + nonce + exact body. Core проверяет freshness/replay, сам resolve'ит internal UUID по Telegram ID и не принимает `user_id`, цену или число начисляемых credits от adapter. Операции AI идемпотентны по `request_id`, платежи — по `telegram_payment_charge_id`.

## Cloud backup and sync

После входа user-owned данные можно синхронизировать с серверным storage:

- schedule preferences;
- lessons и заметки;
- deadlines и calendar state;
- theme/settings;
- ограниченное Student AI state, если для него есть понятная retention policy.

Каждая синхронизируемая запись должна иметь `user_id`, `updated_at`, стабильный ID и возможность удаления. Для первого этапа достаточно last-write-wins с серверным timestamp и явным журналом конфликтов; сложный collaborative sync сейчас не нужен.

## Этапы внедрения

1. ✅ Добавить серверные users/sessions и проверку Telegram login payload.
2. ✅ Заменить `local-demo-user` на identity из session dependency.
3. ✅ Добавить Telegram account link и локальную adapter boundary к credits ledger.
4. ✅ Добавить unified ledger, HMAC bridge и authoritative Stars catalog.
5. Подключить default-off Telegram adapter с durable payment outbox и провести ручной cutover.
6. Подключить cloud persistence только в отдельном scope.

## Ещё не подключено

- production Telegram OIDC widget/callback и account recovery;
- перенос реальных Telegram-пользователей;
- синхронизация существующего SQLite-файла бота;
- списание реальных credits;
- cloud deployment и backup scheduler.

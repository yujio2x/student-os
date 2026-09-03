# Telegram login, credits и cloud backup

Статус: server sessions, legacy HMAC boundary и OIDC Authorization Code + PKCE с account UI реализованы. Реальная production-проверка требует credentials/domain.

## Настройка текущего входа

В BotFather → Login Widget зарегистрируйте HTTPS origin и точный callback
`https://YOUR-DOMAIN/api/auth/telegram/callback`; сохраните выданные Client ID/Secret
в `TELEGRAM_CLIENT_ID`, `TELEGRAM_CLIENT_SECRET`, а callback — в `TELEGRAM_REDIRECT_URI`.
Алгоритм ID token — RS256. `APP_ENV=production` включает Secure cookies; development
flags выключить. Не копируйте секреты в репозиторий. Источник: [Telegram Login](https://core.telegram.org/bots/telegram-login).

Кнопка Settings запускает серверный flow с одноразовым state, PKCE verifier и отдельной
HttpOnly SameSite=Lax cookie на пять минут. Callback привязан также к исходной сессии,
если она была; проверяет RS256 signature, issuer, audience, expiry, issue time и числовой
Telegram `id` (не OIDC `sub`). Никакие browser profile claims сами по себе не доверены.
Raw ID/access tokens не сохраняются. State расходуется один раз перед обменом code.

При текущей сессии flow связывает Telegram с её internal user; конфликт с существующим
аккаунтом отклоняется без переноса/слияния данных. Для входа в уже существующий аккаунт
нужно выйти и войти через Telegram. Успешный вход обновляет session/CSRF. Удаление
единственной Telegram identity остаётся запрещённым. Logout не удаляет данные.

Settings показывает trial/credits/unlimited, покупку и ручное обновление баланса.
Без credentials кнопка честно disabled; в production вместо dev-login показывается
экран входа. Отказ, истечение и конфликт отображаются без секретных параметров URL.
Существующие HMAC endpoints сохранены для совместимости; новая UI использует OIDC.

Не логируйте callback query string, code, token response или cookies на reverse proxy.
Штатные Procfile/run.py отключают Uvicorn access log, который иначе включал бы code.
Live login/owner verification проверяются владельцем в staging; fixtures не заменяют это.

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
5. ✅ Default-off Telegram adapter с durable payment outbox, text/photo/feedback; ручной cutover ещё не выполнен.
6. Подключить cloud persistence только в отдельном scope.

## Ещё не подключено

- live-проверка реализованного OIDC callback с production credentials/domain; автоматическое слияние аккаунтов не реализовано;
- перенос реальных Telegram-пользователей;
- миграция legacy SQLite намеренно не выполняется: он остаётся archive/rollback;
- списание реальных credits;
- cloud deployment и backup scheduler.

# Telegram login, credits и cloud backup

Статус: архитектурное направление принято; production auth в текущий sprint не реализуется.

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

Текущие таблицы уже содержат `user_id`. Значение `local-demo-user` является временной локальной заглушкой и должно заменяться сервером после появления session/auth слоя.

## Login flow

1. Пользователь запускает вход через официальный Telegram login flow.
2. Backend проверяет подпись Telegram, свежесть `auth_date` и допустимый origin.
3. Backend создаёт или находит Student OS user и сохраняет связь с `telegram_user_id`.
4. Браузер получает серверную session cookie с `HttpOnly`, `Secure` и подходящим `SameSite`.
5. Клиент никогда не выбирает `user_id` самостоятельно и не считается источником истины для Telegram identity.

Нельзя принимать Telegram ID или баланс credits из непроверенного browser payload. Bot token, OpenAI key и session secrets хранятся только в environment/secrets storage.

## Credits integration

Рекомендуемая граница — отдельный `StudentAIEntitlementService` в application layer:

- `get_balance(user_id)`;
- `reserve_credit(user_id, request_id)`;
- `commit_usage(request_id)`;
- `release_reservation(request_id)`.

Первый adapter может работать с существующим ledger `student-ai-bot`, но Student AI не должен напрямую импортировать Telegram handlers или payment UI. Операции должны быть идемпотентными по `request_id`, чтобы retry не списывал credits дважды.

## Cloud backup and sync

После входа user-owned данные можно синхронизировать с серверным storage:

- schedule preferences;
- lessons и заметки;
- deadlines и calendar state;
- theme/settings;
- ограниченное Student AI state, если для него есть понятная retention policy.

Каждая синхронизируемая запись должна иметь `user_id`, `updated_at`, стабильный ID и возможность удаления. Для первого этапа достаточно last-write-wins с серверным timestamp и явным журналом конфликтов; сложный collaborative sync сейчас не нужен.

## Этапы внедрения

1. Добавить серверные users/sessions и проверку Telegram login payload.
2. Заменить `local-demo-user` на identity из session dependency.
3. Добавить Telegram account link и adapter к credits ledger.
4. Подключить cloud persistence и миграцию локальных данных после подтверждения пользователем.
5. Провести отдельный security review: replay, session fixation, CSRF, user isolation, duplicate charging и account unlink/relink.

## Не входит в текущий checkpoint

- production cookies/session storage;
- перенос реальных Telegram-пользователей;
- синхронизация существующего SQLite-файла бота;
- списание реальных credits;
- cloud deployment и backup scheduler.

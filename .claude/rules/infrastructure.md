<important if="deploying, connecting to servers, or running remote commands">
- App Server (77.233.212.61, Timeweb Cloud) — ЕДИНСТВЕННЫЙ сервер для деплоя. Подключение: `ssh timeweb`.
- DB Server (89.23.119.253:6433) — ТОЛЬКО ЧТЕНИЕ. Сторонний сервер подрядчика. Нельзя деплоить, писать данные, менять конфиг.
</important>

- Конфигурация — только `shared/config.py` (shim: `scripts/config.py`, читает из `.env`).
- Скрипты запускаются из корня проекта: `python scripts/<name>.py`.
- Секреты — ТОЛЬКО в `.env`. Никогда не хардкодить.
- `.env.example` — только плейсхолдеры.
- Supabase: RLS включён на всех таблицах. При создании новой — обязательно RLS + политики. Роль `anon` заблокирована.
- Полная документация: `docs/infrastructure.md`.

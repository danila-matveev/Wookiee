# Wookiee SKU Database

База данных спецификаций товаров Wookiee с подключением к Supabase.

---

## Быстрый старт

### 1. Установка

```bash
cd sku_database
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настройка подключения

Создай файл `.env`:

```env
POSTGRES_HOST=aws-0-xx-xxx-x.pooler.supabase.com
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres.xxxxx
POSTGRES_PASSWORD=your_password
```

### 3. Проверка

```bash
python db.py
```

---

## CLI Команды

```bash
python db.py status          # Статус подключения
python db.py colors          # Статистика цветов
python db.py models          # Список моделей
python db.py tables          # Все таблицы
python db.py views           # Список VIEW
python db.py query "SQL"     # SQL запрос
python db.py backup          # Создать backup
```

### Примеры

```bash
# Цвета со статусом "Продается"
python db.py query "SELECT color_code, cvet FROM cveta c
JOIN statusy s ON c.status_id=s.id WHERE s.nazvanie='Продается'"

# Топ моделей по SKU
python db.py query "SELECT mo.kod, COUNT(t.id) as sku
FROM modeli_osnova mo
JOIN modeli m ON m.model_osnova_id=mo.id
JOIN artikuly a ON a.model_id=m.id
JOIN tovary t ON t.artikul_id=a.id
GROUP BY mo.kod ORDER BY sku DESC LIMIT 10"
```

---

## Структура проекта

```
sku_database/
├── db.py                   # CLI команда (главная!)
├── .env                    # Настройки подключения
├── requirements.txt        # Зависимости
│
├── config/
│   ├── database.py         # Подключение к БД
│   └── mapping.py          # Маппинг Excel → БД
│
├── database/
│   ├── models.py           # SQLAlchemy модели
│   ├── schema.sql          # SQL схема (DDL)
│   └── triggers.sql        # Триггеры версионирования
│
└── scripts/
    ├── migrate_data.py     # Импорт из Excel
    ├── deploy_to_supabase.py # Развертывание схемы в Supabase
    └── migrations/         # Миграции БД
        ├── 001_add_tip_kollekcii.py
        ├── 002_sync_color_statuses.py
        ├── 003_fix_database_issues.py
        ├── 004_fix_data_integrity.py
        ├── 005_fix_supabase_security.py
        └── 006_fix_remaining_security.py
```

---

## База данных

### Иерархия

```
modeli_osnova (Vuki, Moon, Ruby...)      → 22
    └── modeli (Vuki-ИП, VukiN-ООО...)   → 40
            └── artikuly (модель + цвет) → 478
                    └── tovary (SKU)     → 1450
```

### Основные таблицы

| Таблица | Описание | Записей |
|---------|----------|---------|
| `cveta` | Справочник цветов | 137 |
| `modeli_osnova` | Базовые модели | 22 |
| `modeli` | Вариации моделей | 40 |
| `artikuly` | Артикулы | 478 |
| `tovary` | SKU | 1450 |
| `statusy` | Статусы | 7 |

### Типы коллекций

| Тип | Модели |
|-----|--------|
| `tricot` | Vuki, Moon, Ruby, Joy, Space, Alice, Valery, Set Vuki/Moon/Ruby |
| `seamless_wendy` | Wendy, Bella, Charlotte, Eva, Lana, Mia, Jess, Angelina |
| `seamless_audrey` | Audrey |

### Семейства цветов

| Семейство | Коды | Описание |
|-----------|------|----------|
| tricot | 1-39, w1-w13, P1-P9 | Трикотаж |
| jelly | WE001-WE020 | Бесшовные Wendy |
| audrey | AU001-AU020 | Бесшовные Audrey |

---

## Использование в Python

```python
from config.database import execute_sql, get_session
from database.models import Cvet, Model

# SQL запрос
result = execute_sql("SELECT * FROM cveta WHERE status_id = 1")

# ORM
session = get_session()
colors = session.query(Cvet).filter(Cvet.status_id == 1).all()
session.close()
```

---

## Обновление данных

```bash
# Импорт из Excel
python db.py import-excel

# Синхронизация статусов
python db.py sync-colors

# Backup
python db.py backup --output backup.sql
```

---

## Безопасность Supabase

### Текущая конфигурация (после миграций 005-006)

| Параметр | Значение |
|----------|----------|
| RLS (Row Level Security) | Включён на всех 16 таблицах |
| Роль `anon` | Полностью заблокирована (0 прав) |
| Роль `authenticated` | Только SELECT (чтение) |
| Роль `postgres` (service_role) | Полный доступ (для Python-скриптов) |
| Публичные функции | Закрыты для `anon` и `public` |

### Как работает подключение

Python-скрипты подключаются через Supabase Connection Pooler с ролью `postgres` (service_role). RLS **не применяется** к этой роли, поэтому скрипты работают без ограничений.

Supabase REST API (`https://<project>.supabase.co/rest/v1/`) всегда работает, даже если мы его не используем. Без RLS любой с `anon key` мог бы читать и модифицировать все данные через этот API.

### Правила при добавлении новых таблиц

При создании новой таблицы в `public` схеме **обязательно**:

```sql
-- 1. Включить RLS
ALTER TABLE public.new_table ENABLE ROW LEVEL SECURITY;

-- 2. Создать политику для postgres (service_role)
CREATE POLICY service_role_full_access_new_table ON public.new_table
    FOR ALL TO postgres USING (true) WITH CHECK (true);

-- 3. Создать политику для authenticated (только чтение)
CREATE POLICY authenticated_select_new_table ON public.new_table
    FOR SELECT TO authenticated USING (true);

-- 4. НЕ давать прав anon
-- (default privileges уже настроены на запрет)
```

### Миграции безопасности

| Миграция | Описание | Дата |
|----------|----------|------|
| `005_fix_supabase_security.py` | RLS + revoke grants + policies | 11.02.2026 |
| `006_fix_remaining_security.py` | SECURITY DEFINER views + functions + sequences | 25.02.2026 |

Запуск: `python scripts/migrations/005_fix_supabase_security.py`

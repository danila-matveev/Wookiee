<important if="writing financial calculations: revenue, margin, cost, price, discount, commission, logistics cost, penalty, or any money-related math">
Денежные вычисления — ТОЛЬКО через Decimal.
float даёт ошибки округления, которые накапливаются через цепочку вычислений.
from decimal import Decimal, ROUND_HALF_UP
Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP).
Исключение: SQL-запросы (PostgreSQL numeric точнее Python float, результат из БД допустимо обрабатывать как float для отображения).
</important>

<important if="writing or modifying public functions in shared/, services/, or agents/ modules">
Type hints на public API: все аргументы и return type.
Внутренние helper-функции (с _ префиксом) — type hints опциональны.
</important>

<important if="writing async code or working with aiogram/aiohttp/asyncpg">
Async паттерны:
- async with для сессий и соединений (не ручной close)
- asyncio.gather() для параллельных запросов, НЕ последовательные await в цикле
- asyncio.wait_for(coro, timeout=30) на все внешние вызовы (API, DB)
- Никогда time.sleep() в async-коде — только asyncio.sleep()
</important>

- Import ordering: stdlib, third-party, local (shared, services, agents). Пустая строка между группами.
- f-strings вместо .format() и %.
- pathlib.Path вместо os.path.join для работы с путями.
- except Exception as e: если ловишь, ВСЕГДА либо re-raise, либо return с индикатором ошибки (не молчаливый None или пустой список).

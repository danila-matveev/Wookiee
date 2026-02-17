"""
Healthcheck для Docker — проверяет работоспособность Oleg Agent.

Используется в docker-compose.yml:
  healthcheck:
    test: ["CMD", "python", "/app/deploy/healthcheck_agent.py"]

Проверяет:
  1. PID-файл oleg_agent.pid существует и процесс жив
  2. PostgreSQL WB доступен
  3. PostgreSQL OZON доступен

НЕ проверяет Telegram (агент не зависит от Telegram).
"""
import os
import sys


def check_pid_alive() -> bool:
    """Проверяет что PID-файл агента существует и процесс жив."""
    pid_path = "/app/agents/oleg/logs/oleg_agent.pid"
    if not os.path.exists(pid_path):
        print("FAIL: Agent PID file not found")
        return False
    try:
        pid = int(open(pid_path).read().strip())
        os.kill(pid, 0)  # signal 0 = проверка существования
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        print("FAIL: Agent PID process not alive")
        return False


def check_postgres(db_name: str, label: str) -> bool:
    """Проверяет доступность PostgreSQL."""
    try:
        import psycopg2
    except ImportError:
        print(f"SKIP: psycopg2 not available for {label}")
        return True

    host = os.getenv("DB_HOST", "")
    port = int(os.getenv("DB_PORT", "6433"))
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")

    if not all([host, user, password]):
        print(f"FAIL: DB credentials not set for {label}")
        return False

    try:
        conn = psycopg2.connect(
            host=host, port=port, user=user,
            password=password, database=db_name,
            connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"FAIL: {label} DB error: {e}")
        return False


def main():
    results = {}

    results["pid"] = check_pid_alive()

    db_wb = os.getenv("DB_NAME_WB", "pbi_wb_wookiee")
    db_ozon = os.getenv("DB_NAME_OZON", "pbi_ozon_wookiee")
    results["db_wb"] = check_postgres(db_wb, "WB")
    results["db_ozon"] = check_postgres(db_ozon, "OZON")

    failed = [k for k, v in results.items() if not v]

    if failed:
        print(f"UNHEALTHY: {', '.join(failed)}")
        sys.exit(1)

    print("HEALTHY")
    sys.exit(0)


if __name__ == "__main__":
    main()

# WB Logistics Toolkit — Plan 1: Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `wb-logistics-toolkit` repo with a fully working shared infrastructure layer: WB API client, multi-cabinet config, Supabase client, and KTR/KRP coefficient table loader.

**Architecture:** New standalone Python repo at `~/Projects/wb-logistics-toolkit/`. All shared code lives in `shared/`. The WB API client is token-agnostic (`WBClient(token=...)`). Cabinet configs live in `cabinets.yaml` (non-secret) + `.env` (secrets). KTR/KRP table loads from Supabase `wb_coeff_table` at runtime with module-level cache.

**Tech Stack:** Python 3.11+, httpx, supabase-py, PyYAML, python-dotenv, pytest, pytest-mock

---

## File Map

| File | Responsibility |
|------|----------------|
| `wb-logistics-toolkit/.gitignore` | Exclude .env, credentials.json, *.db, cache/ |
| `wb-logistics-toolkit/requirements.txt` | All dependencies pinned |
| `wb-logistics-toolkit/.env.example` | Template for secrets |
| `wb-logistics-toolkit/cabinets.yaml` | Example cabinet config (commitable) |
| `wb-logistics-toolkit/warehouse_status.yaml` | All WB warehouses: FO, availability, daily redistribution limit |
| `wb-logistics-toolkit/check_setup.py` | Validates env, files, Supabase connection |
| `wb-logistics-toolkit/shared/__init__.py` | Empty |
| `wb-logistics-toolkit/shared/config.py` | Reads cabinets.yaml + .env → `Cabinet` dataclass |
| `wb-logistics-toolkit/shared/wb_api/__init__.py` | Empty |
| `wb-logistics-toolkit/shared/wb_api/client.py` | `WBClient(token)` — base HTTP client |
| `wb-logistics-toolkit/shared/wb_api/orders.py` | `fetch_orders(client, date_from, date_to)` |
| `wb-logistics-toolkit/shared/wb_api/tariffs.py` | `fetch_box_tariffs(client)` |
| `wb-logistics-toolkit/shared/wb_api/content.py` | `fetch_nm_volumes(client, nm_ids)` |
| `wb-logistics-toolkit/shared/wb_api/warehouse_remains.py` | `fetch_warehouse_remains(client)` |
| `wb-logistics-toolkit/shared/wb_api/reports.py` | `fetch_report(client, date_from, date_to)` |
| `wb-logistics-toolkit/shared/supabase.py` | `get_supabase_client()` singleton |
| `wb-logistics-toolkit/shared/coeff_table.py` | `get_ktr_krp(loc_pct)` — loads from Supabase, cached |
| `wb-logistics-toolkit/tests/shared/test_config.py` | Tests for config loading |
| `wb-logistics-toolkit/tests/shared/wb_api/test_client.py` | Tests for WB API client |
| `wb-logistics-toolkit/tests/shared/test_coeff_table.py` | Tests for KTR/KRP lookup |

---

## Task 1: Create repo skeleton

**Files:**
- Create: `~/Projects/wb-logistics-toolkit/` (new git repo)
- Create: `.gitignore`, `requirements.txt`, `.env.example`, `cabinets.yaml`

- [ ] **Step 1.1: Create repo and base files**

```bash
mkdir -p ~/Projects/wb-logistics-toolkit
cd ~/Projects/wb-logistics-toolkit
git init
mkdir -p shared/wb_api tests/shared/wb_api localization/data/cache audit docs
touch shared/__init__.py shared/wb_api/__init__.py
touch tests/__init__.py tests/shared/__init__.py tests/shared/wb_api/__init__.py
```

- [ ] **Step 1.2: Create `.gitignore`**

```
.env
credentials.json
*.db
localization/data/cache/
__pycache__/
*.pyc
.pytest_cache/
dist/
*.egg-info/
.DS_Store
```

- [ ] **Step 1.3: Create `requirements.txt`**

```
httpx>=0.27.0
pandas>=2.2.0
openpyxl>=3.1.2
google-auth>=2.29.0
gspread>=6.1.0
supabase>=2.4.0
python-dotenv>=1.0.1
PyYAML>=6.0.1
pytest>=8.1.0
pytest-mock>=3.14.0
```

- [ ] **Step 1.4: Create `.env.example`**

```bash
# WB API tokens — name matches cabinet `name` in cabinets.yaml (uppercase)
WB_TOKEN_OOO=eyJ...
WB_TOKEN_IP=eyJ...

# Google Service Account credentials file path
GOOGLE_CREDENTIALS_PATH=credentials.json

# Supabase — для истории тарифов и таблицы КТР/КРП
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJ...
```

- [ ] **Step 1.5: Create `cabinets.yaml`**

```yaml
# Конфигурация кабинетов WB.
# Токены хранятся в .env: WB_TOKEN_{NAME_UPPER}
# Этот файл можно коммитить — секретов нет.
cabinets:
  - name: ooo
    sheet_id: "1TMadxTXPYnuGTvnMZT9Ny7eL4KbvsjK2XsuRjpRmnM0"
  - name: ip
    sheet_id: "YOUR_SHEET_ID_HERE"
```

- [ ] **Step 1.6: Install dependencies**

```bash
cd ~/Projects/wb-logistics-toolkit
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: All packages install without errors.

- [ ] **Step 1.7: Commit**

```bash
git add .
git commit -m "chore: init repo skeleton with dependencies and config templates"
```

---

## Task 2: `warehouse_status.yaml` — склады и лимиты

**Files:**
- Create: `~/Projects/wb-logistics-toolkit/warehouse_status.yaml`

- [ ] **Step 2.1: Create `warehouse_status.yaml`**

Содержит все известные склады WB с их ФО, статусом и дневным лимитом перераспределения.

```yaml
# Справочник складов WB.
# available: false — склад исключается из рекомендаций по перестановкам.
# redistribution_limit_per_day — из WB Partners → Тарифный конструктор.
warehouses:
  # Центральный ФО
  - name: Коледино
    fd: Центральный
    available: true
    redistribution_limit_per_day: 100000
  - name: Электросталь
    fd: Центральный
    available: true
    redistribution_limit_per_day: 98900
  - name: Тула
    fd: Центральный
    available: true
    redistribution_limit_per_day: 100000
  - name: Котовск
    fd: Центральный
    available: true
    redistribution_limit_per_day: 499300
  - name: Рязань (Тюшевское)
    fd: Центральный
    available: true
    redistribution_limit_per_day: 99600
  - name: Белые Столбы
    fd: Центральный
    available: true
    redistribution_limit_per_day: 5000
  - name: Подольск
    fd: Центральный
    available: true
    redistribution_limit_per_day: 5000

  # Южный + Северо-Кавказский ФО
  - name: Краснодар (Тихорецкая)
    fd: Южный + Северо-Кавказский
    available: true
    redistribution_limit_per_day: 499000
  - name: Краснодар
    fd: Южный + Северо-Кавказский
    available: true
    redistribution_limit_per_day: 10000
  - name: Невинномысск
    fd: Южный + Северо-Кавказский
    available: true
    redistribution_limit_per_day: 100000
  - name: Волгоград
    fd: Южный + Северо-Кавказский
    available: true
    redistribution_limit_per_day: 49500

  # Приволжский ФО
  - name: Казань
    fd: Приволжский
    available: true
    redistribution_limit_per_day: 10000
    note: "Дорогой склад (~225%), но высокая локализация ПФО ~95%"
  - name: Самара (Новосемейкино)
    fd: Приволжский
    available: true
    redistribution_limit_per_day: 100000
  - name: Сарапул
    fd: Приволжский
    available: true
    redistribution_limit_per_day: 100000
  - name: Пенза
    fd: Приволжский
    available: true
    redistribution_limit_per_day: 20000

  # Северо-Западный ФО
  - name: Склад СПБ Шушары Московское
    fd: Северо-Западный
    available: true
    redistribution_limit_per_day: 4800
  - name: Санкт-Петербург (Шушары)
    fd: Северо-Западный
    available: true
    redistribution_limit_per_day: 4800
  - name: СПб Шушары
    fd: Северо-Западный
    available: true
    redistribution_limit_per_day: 4800
  - name: Калининград
    fd: Северо-Западный
    available: true
    redistribution_limit_per_day: 5000

  # Уральский ФО
  - name: Екатеринбург - Перспективный 12
    fd: Уральский
    available: true
    redistribution_limit_per_day: 100000
  - name: Екатеринбург - Перспективная 14
    fd: Уральский
    available: true
    redistribution_limit_per_day: 100000
  - name: Екатеринбург
    fd: Уральский
    available: true
    redistribution_limit_per_day: 5000

  # Дальневосточный + Сибирский ФО
  - name: Новосибирск
    fd: Дальневосточный + Сибирский
    available: false
    reason: "Закрыт WB для поставок СФО (май 2026)"
    redistribution_limit_per_day: 5000
  - name: Хабаровск
    fd: Дальневосточный + Сибирский
    available: true
    redistribution_limit_per_day: 5000
  - name: Барнаул
    fd: Дальневосточный + Сибирский
    available: true
    redistribution_limit_per_day: 5000
  - name: Владивосток
    fd: Дальневосточный + Сибирский
    available: true
    redistribution_limit_per_day: 5000
```

- [ ] **Step 2.2: Commit**

```bash
git add warehouse_status.yaml
git commit -m "feat: add warehouse_status.yaml with all WB warehouses and redistribution limits"
```

---

## Task 3: `shared/config.py` — конфиг кабинетов

**Files:**
- Create: `shared/config.py`
- Create: `tests/shared/test_config.py`

- [ ] **Step 3.1: Write failing tests**

```python
# tests/shared/test_config.py
import os
import pytest
import yaml
from pathlib import Path

from shared.config import load_cabinets, get_cabinet, Cabinet


SAMPLE_YAML = """
cabinets:
  - name: test_shop
    sheet_id: "1AbCde"
  - name: other
    sheet_id: "2XyZab"
"""


@pytest.fixture
def cabinets_file(tmp_path):
    f = tmp_path / "cabinets.yaml"
    f.write_text(SAMPLE_YAML)
    return f


def test_load_cabinets_returns_cabinet_dataclasses(cabinets_file, monkeypatch):
    monkeypatch.setenv("WB_TOKEN_TEST_SHOP", "token_aaa")
    monkeypatch.setenv("WB_TOKEN_OTHER", "token_bbb")
    cabinets = load_cabinets(cabinets_file)
    assert len(cabinets) == 2
    assert isinstance(cabinets[0], Cabinet)


def test_load_cabinets_maps_token_from_env(cabinets_file, monkeypatch):
    monkeypatch.setenv("WB_TOKEN_TEST_SHOP", "token_aaa")
    monkeypatch.setenv("WB_TOKEN_OTHER", "token_bbb")
    cabinets = load_cabinets(cabinets_file)
    assert cabinets[0].wb_token == "token_aaa"
    assert cabinets[0].sheet_id == "1AbCde"
    assert cabinets[0].name == "test_shop"


def test_load_cabinets_raises_if_token_missing(cabinets_file, monkeypatch):
    monkeypatch.delenv("WB_TOKEN_TEST_SHOP", raising=False)
    monkeypatch.delenv("WB_TOKEN_OTHER", raising=False)
    with pytest.raises(ValueError, match="WB_TOKEN_TEST_SHOP"):
        load_cabinets(cabinets_file)


def test_get_cabinet_returns_correct_cabinet(cabinets_file, monkeypatch):
    monkeypatch.setenv("WB_TOKEN_TEST_SHOP", "token_aaa")
    monkeypatch.setenv("WB_TOKEN_OTHER", "token_bbb")
    cab = get_cabinet("other", cabinets_file)
    assert cab.name == "other"
    assert cab.wb_token == "token_bbb"


def test_get_cabinet_raises_for_unknown_name(cabinets_file, monkeypatch):
    monkeypatch.setenv("WB_TOKEN_TEST_SHOP", "token_aaa")
    monkeypatch.setenv("WB_TOKEN_OTHER", "token_bbb")
    with pytest.raises(ValueError, match="not found"):
        get_cabinet("nonexistent", cabinets_file)


def test_load_warehouse_statuses(tmp_path):
    from shared.config import load_warehouse_statuses, WarehouseStatus
    wh_file = tmp_path / "warehouse_status.yaml"
    wh_file.write_text("""
warehouses:
  - name: Коледино
    fd: Центральный
    available: true
    redistribution_limit_per_day: 100000
  - name: Новосибирск
    fd: Дальневосточный + Сибирский
    available: false
    reason: Закрыт
    redistribution_limit_per_day: 5000
""")
    statuses = load_warehouse_statuses(wh_file)
    assert len(statuses) == 2
    koledino = statuses["Коледино"]
    assert koledino.available is True
    assert koledino.redistribution_limit_per_day == 100000
    nsk = statuses["Новосибирск"]
    assert nsk.available is False


def test_load_warehouse_statuses_available_only(tmp_path):
    from shared.config import load_warehouse_statuses
    wh_file = tmp_path / "warehouse_status.yaml"
    wh_file.write_text("""
warehouses:
  - name: Коледино
    fd: Центральный
    available: true
    redistribution_limit_per_day: 100000
  - name: Новосибирск
    fd: Дальневосточный + Сибирский
    available: false
    redistribution_limit_per_day: 5000
""")
    statuses = load_warehouse_statuses(wh_file, available_only=True)
    assert "Коледино" in statuses
    assert "Новосибирск" not in statuses
```

- [ ] **Step 3.2: Run test to confirm it fails**

```bash
cd ~/Projects/wb-logistics-toolkit
source .venv/bin/activate
pytest tests/shared/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'shared.config'`

- [ ] **Step 3.3: Implement `shared/config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Cabinet:
    name: str
    wb_token: str
    sheet_id: str


@dataclass(frozen=True)
class WarehouseStatus:
    name: str
    fd: str
    available: bool
    redistribution_limit_per_day: int
    reason: str = ""
    note: str = ""


def load_cabinets(cabinets_path: str | Path = "cabinets.yaml") -> list[Cabinet]:
    path = Path(cabinets_path)
    with open(path) as f:
        data = yaml.safe_load(f)

    result: list[Cabinet] = []
    for c in data["cabinets"]:
        name: str = c["name"]
        token_key = f"WB_TOKEN_{name.upper()}"
        token = os.environ.get(token_key)
        if not token:
            raise ValueError(
                f"Missing env var: {token_key} (required for cabinet '{name}')"
            )
        result.append(Cabinet(name=name, wb_token=token, sheet_id=c["sheet_id"]))
    return result


def get_cabinet(
    name: str, cabinets_path: str | Path = "cabinets.yaml"
) -> Cabinet:
    for cab in load_cabinets(cabinets_path):
        if cab.name == name:
            return cab
    raise ValueError(f"Cabinet '{name}' not found in {cabinets_path}")


def load_warehouse_statuses(
    warehouse_path: str | Path = "warehouse_status.yaml",
    available_only: bool = False,
) -> dict[str, WarehouseStatus]:
    path = Path(warehouse_path)
    with open(path) as f:
        data = yaml.safe_load(f)

    result: dict[str, WarehouseStatus] = {}
    for w in data["warehouses"]:
        status = WarehouseStatus(
            name=w["name"],
            fd=w["fd"],
            available=bool(w.get("available", True)),
            redistribution_limit_per_day=int(
                w.get("redistribution_limit_per_day", 5000)
            ),
            reason=w.get("reason", ""),
            note=w.get("note", ""),
        )
        if available_only and not status.available:
            continue
        result[status.name] = status
    return result
```

- [ ] **Step 3.4: Run tests to confirm they pass**

```bash
pytest tests/shared/test_config.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 3.5: Commit**

```bash
git add shared/config.py tests/shared/test_config.py
git commit -m "feat: add Cabinet + WarehouseStatus config loaders with tests"
```

---

## Task 4: `shared/wb_api/client.py` — WB API клиент

**Files:**
- Create: `shared/wb_api/client.py`
- Create: `tests/shared/wb_api/test_client.py`

- [ ] **Step 4.1: Write failing tests**

```python
# tests/shared/wb_api/test_client.py
import pytest
import httpx
from unittest.mock import patch, MagicMock

from shared.wb_api.client import WBClient


def test_client_sets_authorization_header():
    client = WBClient(token="test_token_abc")
    assert client._headers["Authorization"] == "test_token_abc"


def test_client_get_calls_correct_url(respx_mock=None):
    client = WBClient(token="tok")
    mock_response = {"data": [{"id": 1}]}

    with patch("httpx.Client") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.return_value.__enter__.return_value.get.return_value = mock_resp

        result = client.get(
            base="https://statistics-api.wildberries.ru",
            path="/api/v1/supplier/orders",
            params={"dateFrom": "2026-01-01"},
        )

    assert result == mock_response
    call_args = mock_httpx.return_value.__enter__.return_value.get.call_args
    assert call_args[0][0] == "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
    assert call_args[1]["params"]["dateFrom"] == "2026-01-01"


def test_client_raises_on_http_error():
    client = WBClient(token="tok")

    with patch("httpx.Client") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock()
        )
        mock_httpx.return_value.__enter__.return_value.get.return_value = mock_resp

        with pytest.raises(httpx.HTTPStatusError):
            client.get(
                base="https://statistics-api.wildberries.ru",
                path="/api/v1/supplier/orders",
            )


def test_client_default_timeout_is_30():
    client = WBClient(token="tok")
    assert client.timeout == 30.0


def test_client_custom_timeout():
    client = WBClient(token="tok", timeout=60.0)
    assert client.timeout == 60.0
```

- [ ] **Step 4.2: Run test to confirm it fails**

```bash
pytest tests/shared/wb_api/test_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'shared.wb_api.client'`

- [ ] **Step 4.3: Implement `shared/wb_api/client.py`**

```python
from __future__ import annotations

from typing import Any

import httpx


class WBClient:
    """Token-agnostic WB API HTTP client.

    Usage:
        client = WBClient(token="eyJ...")
        data = client.get(base=WBClient.STATS_URL, path="/api/v1/supplier/orders",
                          params={"dateFrom": "2026-01-01"})
    """

    STATS_URL = "https://statistics-api.wildberries.ru"
    CONTENT_URL = "https://content-api.wildberries.ru"
    SUPPLY_URL = "https://supplies-api.wildberries.ru"

    def __init__(self, token: str, timeout: float = 30.0) -> None:
        self.token = token
        self.timeout = timeout
        self._headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

    def get(
        self,
        base: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """GET request, returns parsed JSON. Raises httpx.HTTPStatusError on 4xx/5xx."""
        url = f"{base}{path}"
        with httpx.Client(timeout=self.timeout) as http:
            response = http.get(url, headers=self._headers, params=params or {})
            response.raise_for_status()
            return response.json()

    def post(
        self,
        base: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """POST request, returns parsed JSON. Raises httpx.HTTPStatusError on 4xx/5xx."""
        url = f"{base}{path}"
        with httpx.Client(timeout=self.timeout) as http:
            response = http.post(url, headers=self._headers, json=json or {})
            response.raise_for_status()
            return response.json()
```

- [ ] **Step 4.4: Run tests to confirm they pass**

```bash
pytest tests/shared/wb_api/test_client.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 4.5: Commit**

```bash
git add shared/wb_api/client.py tests/shared/wb_api/test_client.py
git commit -m "feat: add WBClient with token-agnostic GET/POST and tests"
```

---

## Task 5: WB API endpoints — orders, tariffs, warehouse_remains, content, reports

**Files:**
- Create: `shared/wb_api/orders.py`
- Create: `shared/wb_api/tariffs.py`
- Create: `shared/wb_api/warehouse_remains.py`
- Create: `shared/wb_api/content.py`
- Create: `shared/wb_api/reports.py`
- Create: `tests/shared/wb_api/test_endpoints.py`

- [ ] **Step 5.1: Write failing tests**

```python
# tests/shared/wb_api/test_endpoints.py
from unittest.mock import MagicMock, patch

from shared.wb_api.client import WBClient
from shared.wb_api.orders import fetch_orders
from shared.wb_api.tariffs import fetch_box_tariffs
from shared.wb_api.warehouse_remains import fetch_warehouse_remains
from shared.wb_api.content import fetch_nm_volumes
from shared.wb_api.reports import fetch_report


def make_client():
    return WBClient(token="test_token")


def test_fetch_orders_calls_correct_endpoint():
    client = make_client()
    mock_data = [{"supplierArticle": "art1", "warehouseName": "Коледино"}]

    with patch.object(client, "get", return_value=mock_data) as mock_get:
        result = fetch_orders(client, date_from="2026-01-01")

    mock_get.assert_called_once()
    call_args = mock_get.call_args
    assert "/api/v1/supplier/orders" in call_args[1].get("path", call_args[0][1])
    assert result == mock_data


def test_fetch_orders_excludes_cancelled_by_default():
    client = make_client()
    raw = [
        {"supplierArticle": "a", "isCancel": False},
        {"supplierArticle": "b", "isCancel": True},
    ]
    with patch.object(client, "get", return_value=raw):
        result = fetch_orders(client, date_from="2026-01-01", exclude_cancelled=True)
    assert len(result) == 1
    assert result[0]["supplierArticle"] == "a"


def test_fetch_box_tariffs_returns_list():
    client = make_client()
    mock_resp = {"response": {"data": {"warehouseList": [
        {"warehouseName": "Коледино", "boxDeliveryBase": 46.0}
    ]}}}
    with patch.object(client, "get", return_value=mock_resp):
        result = fetch_box_tariffs(client)
    assert isinstance(result, list)
    assert result[0]["warehouseName"] == "Коледино"


def test_fetch_warehouse_remains_returns_list():
    client = make_client()
    mock_resp = [{"warehouseName": "Коледино", "nmId": 123, "quantity": 50}]
    with patch.object(client, "get", return_value=mock_resp):
        result = fetch_warehouse_remains(client)
    assert result == mock_resp


def test_fetch_nm_volumes_returns_dict():
    client = make_client()
    mock_resp = {"data": {"cards": [
        {"nmID": 123, "dimensions": {"length": 10, "width": 10, "height": 10}}
    ]}}
    with patch.object(client, "post", return_value=mock_resp):
        result = fetch_nm_volumes(client, nm_ids=[123])
    assert isinstance(result, dict)
    assert 123 in result


def test_fetch_report_returns_list():
    client = make_client()
    mock_data = [{"realizationreport_id": 1, "quantity": 5}]
    with patch.object(client, "get", return_value=mock_data):
        result = fetch_report(client, date_from="2026-01-01", date_to="2026-03-31")
    assert result == mock_data
```

- [ ] **Step 5.2: Run tests to confirm they fail**

```bash
pytest tests/shared/wb_api/test_endpoints.py -v
```

Expected: `ModuleNotFoundError` for all endpoint modules.

- [ ] **Step 5.3: Implement `shared/wb_api/orders.py`**

```python
from __future__ import annotations

from typing import Any

from .client import WBClient


def fetch_orders(
    client: WBClient,
    date_from: str,
    flag: int = 0,
    exclude_cancelled: bool = False,
) -> list[dict[str, Any]]:
    """Fetch supplier orders from WB Statistics API.

    Args:
        client: WBClient instance.
        date_from: ISO date string, e.g. "2026-01-01".
        flag: 0 = all orders since date_from, 1 = only updated orders.
        exclude_cancelled: If True, filter out isCancel=True rows.

    Returns:
        List of order dicts from WB API.
    """
    data = client.get(
        base=WBClient.STATS_URL,
        path="/api/v1/supplier/orders",
        params={"dateFrom": date_from, "flag": flag},
    )
    orders: list[dict[str, Any]] = data if isinstance(data, list) else []
    if exclude_cancelled:
        orders = [o for o in orders if not o.get("isCancel", False)]
    return orders
```

- [ ] **Step 5.4: Implement `shared/wb_api/tariffs.py`**

```python
from __future__ import annotations

from typing import Any

from .client import WBClient


def fetch_box_tariffs(
    client: WBClient,
    date: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch current box delivery tariffs per warehouse.

    Args:
        client: WBClient instance.
        date: ISO date (YYYY-MM-DD). Defaults to today if None.

    Returns:
        List of warehouse tariff dicts with warehouseName, boxDeliveryBase, etc.
    """
    from datetime import date as _date

    params: dict[str, Any] = {"date": date or _date.today().isoformat()}
    data = client.get(
        base=WBClient.SUPPLY_URL,
        path="/api/v1/tariffs/box",
        params=params,
    )
    return data.get("response", {}).get("data", {}).get("warehouseList", [])
```

- [ ] **Step 5.5: Implement `shared/wb_api/warehouse_remains.py`**

```python
from __future__ import annotations

from typing import Any

from .client import WBClient


def fetch_warehouse_remains(client: WBClient) -> list[dict[str, Any]]:
    """Fetch current stock remains per warehouse per nm_id.

    Returns:
        List of dicts with warehouseName, nmId, quantity, etc.
    """
    data = client.get(
        base=WBClient.STATS_URL,
        path="/api/v1/warehouse/remains",
    )
    return data if isinstance(data, list) else []
```

- [ ] **Step 5.6: Implement `shared/wb_api/content.py`**

```python
from __future__ import annotations

from typing import Any

from .client import WBClient


def fetch_nm_volumes(
    client: WBClient,
    nm_ids: list[int],
    batch_size: int = 100,
) -> dict[int, float]:
    """Fetch product dimensions from WB Content API and compute volume in litres.

    Args:
        client: WBClient instance.
        nm_ids: List of WB nm_id (article IDs).
        batch_size: Max IDs per API request (WB limit is 100).

    Returns:
        Dict mapping nm_id → volume in litres (length×width×height / 1000).
    """
    result: dict[int, float] = {}

    for i in range(0, len(nm_ids), batch_size):
        batch = nm_ids[i : i + batch_size]
        resp = client.post(
            base=WBClient.CONTENT_URL,
            path="/content/v2/get/cards/list",
            json={"settings": {"cursor": {"nmIDs": batch, "limit": batch_size}}},
        )
        cards = resp.get("data", {}).get("cards", [])
        for card in cards:
            nm_id = card.get("nmID")
            dims = card.get("dimensions", {})
            length = dims.get("length", 0) or 0
            width = dims.get("width", 0) or 0
            height = dims.get("height", 0) or 0
            if nm_id and length and width and height:
                result[nm_id] = round(length * width * height / 1000, 3)

    return result
```

- [ ] **Step 5.7: Implement `shared/wb_api/reports.py`**

```python
from __future__ import annotations

from typing import Any

from .client import WBClient


def fetch_report(
    client: WBClient,
    date_from: str,
    date_to: str,
    rrdid: int = 0,
    limit: int = 100_000,
) -> list[dict[str, Any]]:
    """Fetch reportDetailByPeriod v5 from WB Statistics API.

    Handles pagination: keeps fetching until no more rows returned.

    Args:
        client: WBClient instance.
        date_from: ISO date string "YYYY-MM-DD".
        date_to: ISO date string "YYYY-MM-DD".
        rrdid: Pagination cursor (rrd_id of last fetched row). Start with 0.
        limit: Rows per page (max 100_000).

    Returns:
        Full list of report rows across all pages.
    """
    all_rows: list[dict[str, Any]] = []
    cursor = rrdid

    while True:
        page = client.get(
            base=WBClient.STATS_URL,
            path="/api/v5/supplier/reportDetailByPeriod",
            params={
                "dateFrom": date_from,
                "dateTo": date_to,
                "rrdid": cursor,
                "limit": limit,
            },
        )
        rows: list[dict[str, Any]] = page if isinstance(page, list) else []
        all_rows.extend(rows)
        if len(rows) < limit:
            break
        cursor = rows[-1].get("rrd_id", cursor)
        if cursor == rrdid:
            break

    return all_rows
```

- [ ] **Step 5.8: Run tests to confirm they pass**

```bash
pytest tests/shared/wb_api/test_endpoints.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5.9: Commit**

```bash
git add shared/wb_api/orders.py shared/wb_api/tariffs.py \
        shared/wb_api/warehouse_remains.py shared/wb_api/content.py \
        shared/wb_api/reports.py tests/shared/wb_api/test_endpoints.py
git commit -m "feat: add WB API endpoint wrappers: orders, tariffs, remains, content, reports"
```

---

## Task 6: `shared/supabase.py` + `shared/coeff_table.py`

**Files:**
- Create: `shared/supabase.py`
- Create: `shared/coeff_table.py`
- Create: `tests/shared/test_coeff_table.py`

- [ ] **Step 6.1: Write failing tests**

```python
# tests/shared/test_coeff_table.py
import pytest
from unittest.mock import patch, MagicMock

import shared.coeff_table as ct


MOCK_ROWS = [
    {"min_loc": 95.0, "max_loc": 100.0, "ktr": 0.50, "krp_pct": 0.0},
    {"min_loc": 80.0, "max_loc": 84.99, "ktr": 0.80, "krp_pct": 0.0},
    {"min_loc": 60.0, "max_loc": 64.99, "ktr": 1.00, "krp_pct": 0.0},
    {"min_loc": 55.0, "max_loc": 59.99, "ktr": 1.05, "krp_pct": 2.00},
    {"min_loc": 0.0,  "max_loc":  4.99, "ktr": 2.20, "krp_pct": 2.50},
]


@pytest.fixture(autouse=True)
def clear_cache():
    ct.clear_cache()
    yield
    ct.clear_cache()


def mock_supabase(rows):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value \
        .lte.return_value.order.return_value.execute.return_value.data = rows
    return mock_client


def test_get_ktr_krp_high_localization():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(97.0)
    assert ktr == 0.50
    assert krp == 0.0


def test_get_ktr_krp_at_80_percent():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(82.0)
    assert ktr == 0.80
    assert krp == 0.0


def test_get_ktr_krp_at_irp_zone():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(57.0)
    assert ktr == 1.05
    assert krp == 2.00


def test_get_ktr_krp_zero_localization():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(0.0)
    assert ktr == 2.20
    assert krp == 2.50


def test_get_ktr_krp_uses_cache_on_second_call():
    mock_sb = mock_supabase(MOCK_ROWS)
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_sb):
        ct.get_ktr_krp(80.0)
        ct.get_ktr_krp(60.0)
    # Supabase should only be called once due to caching
    assert mock_sb.table.call_count == 1


def test_raises_if_table_empty():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase([])):
        with pytest.raises(RuntimeError, match="wb_coeff_table is empty"):
            ct.get_ktr_krp(50.0)


def test_clamp_above_100():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(150.0)
    assert ktr == 0.50


def test_clamp_below_0():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(-10.0)
    assert ktr == 2.20
```

- [ ] **Step 6.2: Run tests to confirm they fail**

```bash
pytest tests/shared/test_coeff_table.py -v
```

Expected: `ModuleNotFoundError: No module named 'shared.coeff_table'`

- [ ] **Step 6.3: Implement `shared/supabase.py`**

```python
from __future__ import annotations

import os
from functools import lru_cache

from supabase import create_client, Client


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Return a cached Supabase client. Reads SUPABASE_URL and SUPABASE_KEY from env."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in environment. "
            "Copy .env.example to .env and fill in your credentials."
        )
    return create_client(url, key)
```

- [ ] **Step 6.4: Implement `shared/coeff_table.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .supabase import get_supabase_client

_cache: list[dict[str, Any]] | None = None


def _load_from_supabase() -> list[dict[str, Any]]:
    client = get_supabase_client()
    response = (
        client.table("wb_coeff_table")
        .select("min_loc, max_loc, ktr, krp_pct")
        .lte("valid_from", date.today().isoformat())
        .order("valid_from", desc=True)
        .execute()
    )
    return response.data or []


def _get_table() -> list[dict[str, Any]]:
    global _cache
    if _cache is not None:
        return _cache
    rows = _load_from_supabase()
    if not rows:
        raise RuntimeError(
            "wb_coeff_table is empty in Supabase. "
            "Run: python audit/etl/import_coeff_table.py"
        )
    _cache = rows
    return _cache


def get_ktr_krp(localization_pct: float) -> tuple[float, float]:
    """Return (КТР, КРП%) for a given per-article localization percentage.

    Args:
        localization_pct: Per-article localization % (0.0 – 100.0).

    Returns:
        (ktr, krp_pct) from the WB coefficient table loaded from Supabase.
    """
    loc = max(0.0, min(100.0, localization_pct))
    for row in _get_table():
        if row["min_loc"] <= loc <= row["max_loc"]:
            return float(row["ktr"]), float(row["krp_pct"])
    return 2.20, 2.50


def clear_cache() -> None:
    """Clear the in-memory coefficient table cache (used in tests)."""
    global _cache
    _cache = None
```

- [ ] **Step 6.5: Run tests to confirm they pass**

```bash
pytest tests/shared/test_coeff_table.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 6.6: Commit**

```bash
git add shared/supabase.py shared/coeff_table.py tests/shared/test_coeff_table.py
git commit -m "feat: add Supabase client and coeff_table loader with caching and tests"
```

---

## Task 7: `check_setup.py` — валидатор окружения

**Files:**
- Create: `check_setup.py`
- Create: `tests/test_check_setup.py`

- [ ] **Step 7.1: Write failing tests**

```python
# tests/test_check_setup.py
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


def test_check_setup_module_importable():
    import check_setup  # noqa: F401


def test_check_env_file_missing(tmp_path, monkeypatch):
    from check_setup import check_env_file
    monkeypatch.chdir(tmp_path)
    ok, msg = check_env_file()
    assert ok is False
    assert ".env" in msg


def test_check_env_file_present(tmp_path, monkeypatch):
    from check_setup import check_env_file
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("WB_TOKEN_OOO=abc")
    ok, msg = check_env_file()
    assert ok is True


def test_check_credentials_missing(tmp_path, monkeypatch):
    from check_setup import check_credentials
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(tmp_path / "creds.json"))
    ok, msg = check_credentials()
    assert ok is False
    assert "credentials" in msg.lower()


def test_check_credentials_present(tmp_path, monkeypatch):
    from check_setup import check_credentials
    creds = tmp_path / "creds.json"
    creds.write_text("{}")
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(creds))
    ok, msg = check_credentials()
    assert ok is True


def test_check_cabinets_yaml_missing(tmp_path, monkeypatch):
    from check_setup import check_cabinets_yaml
    monkeypatch.chdir(tmp_path)
    ok, msg = check_cabinets_yaml()
    assert ok is False


def test_check_credentials_not_in_git_staging(tmp_path, monkeypatch):
    from check_setup import check_credentials_not_staged
    # Should pass when git is not available or no staged file
    ok, msg = check_credentials_not_staged()
    assert isinstance(ok, bool)
```

- [ ] **Step 7.2: Run tests to confirm they fail**

```bash
pytest tests/test_check_setup.py -v
```

Expected: `ModuleNotFoundError: No module named 'check_setup'`

- [ ] **Step 7.3: Implement `check_setup.py`**

```python
#!/usr/bin/env python3
"""Validates that wb-logistics-toolkit is correctly configured.

Run: python check_setup.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def check_env_file() -> tuple[bool, str]:
    if not Path(".env").exists():
        return False, ".env file not found. Copy .env.example to .env and fill in your credentials."
    return True, ".env found"


def check_credentials() -> tuple[bool, str]:
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    if not Path(creds_path).exists():
        return False, (
            f"Google credentials file not found at '{creds_path}'. "
            "Download your Service Account JSON from Google Cloud Console "
            "and set GOOGLE_CREDENTIALS_PATH in .env."
        )
    return True, f"Google credentials found at '{creds_path}'"


def check_credentials_not_staged() -> tuple[bool, str]:
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        staged = result.stdout.strip().splitlines()
        if creds_path in staged:
            return False, (
                f"DANGER: '{creds_path}' is staged for commit! "
                "Run: git reset HEAD credentials.json"
            )
    except Exception:
        pass
    return True, f"'{creds_path}' not staged"


def check_cabinets_yaml() -> tuple[bool, str]:
    if not Path("cabinets.yaml").exists():
        return False, "cabinets.yaml not found. Copy the example and configure your cabinets."
    return True, "cabinets.yaml found"


def check_wb_tokens() -> tuple[bool, str]:
    import yaml
    if not Path("cabinets.yaml").exists():
        return False, "cabinets.yaml missing, cannot check WB tokens"
    with open("cabinets.yaml") as f:
        data = yaml.safe_load(f)
    missing = []
    for cab in data.get("cabinets", []):
        name = cab["name"]
        key = f"WB_TOKEN_{name.upper()}"
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        return False, f"Missing WB tokens in .env: {', '.join(missing)}"
    return True, "All WB tokens found"


def check_supabase() -> tuple[bool, str]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return False, "SUPABASE_URL or SUPABASE_KEY missing in .env"
    try:
        from supabase import create_client
        client = create_client(url, key)
        client.table("wb_coeff_table").select("id").limit(1).execute()
        return True, "Supabase connection OK, wb_coeff_table accessible"
    except Exception as e:
        return False, f"Supabase connection failed: {e}"


def check_warehouse_status_yaml() -> tuple[bool, str]:
    if not Path("warehouse_status.yaml").exists():
        return False, "warehouse_status.yaml not found"
    return True, "warehouse_status.yaml found"


CHECKS = [
    ("📄 .env file", check_env_file),
    ("🔑 Google credentials", check_credentials),
    ("🚫 Credentials not staged", check_credentials_not_staged),
    ("📋 cabinets.yaml", check_cabinets_yaml),
    ("🏭 warehouse_status.yaml", check_warehouse_status_yaml),
    ("🔐 WB API tokens", check_wb_tokens),
    ("🗄️  Supabase connection", check_supabase),
]


def main() -> int:
    print("\n=== WB Logistics Toolkit — Setup Check ===\n")
    all_ok = True
    for label, check_fn in CHECKS:
        ok, msg = check_fn()
        icon = "✅" if ok else "❌"
        print(f"{icon}  {label}: {msg}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("✅ All checks passed. Ready to run!")
        return 0
    else:
        print("❌ Some checks failed. Fix the issues above before running.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7.4: Run tests to confirm they pass**

```bash
pytest tests/test_check_setup.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 7.5: Commit**

```bash
git add check_setup.py tests/test_check_setup.py
git commit -m "feat: add check_setup.py with 7 environment validation checks"
```

---

## Task 8: Full test suite run + README skeleton

**Files:**
- Create: `README.md`

- [ ] **Step 8.1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests pass. Output should look like:
```
tests/shared/test_config.py::test_load_cabinets_returns_cabinet_dataclasses PASSED
tests/shared/test_config.py::test_load_cabinets_maps_token_from_env PASSED
... (all tests)
========================= N passed in X.XXs =========================
```

- [ ] **Step 8.2: Create `README.md`**

```markdown
# WB Logistics Toolkit

Два инструмента для Wildberries-продавца, который хочет перестать переплачивать за логистику.

## Инструменты

### 1. Оптимизатор локализации
Показывает текущий Индекс Локализации (ИЛ), рассчитывает переплату из-за него и строит план перемещений товаров для снижения расходов.

### 2. Аудит переплат
Пересчитывает историческую логистику по официальным тарифам WB. Используется для выявления расхождений и возврата переплат.

## Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/your-org/wb-logistics-toolkit.git
cd wb-logistics-toolkit

# 2. Установить зависимости
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Настроить
cp .env.example .env
# Отредактировать .env и cabinets.yaml

# 4. Проверить настройку
python check_setup.py

# 5. Запустить анализ
python localization/run_analysis.py --cabinet ooo --days 90
```

## Документация

- [Установка](docs/setup.md)
- [Ключевые понятия](docs/concepts.md)
- [Как работать с инструментом](docs/workflow-localization.md)
- [Справочник складов](docs/warehouses.md)
- [Аудит переплат](docs/tool-audit.md)
- [Supabase и тарифы](docs/tariffs-db.md)

## Требования

- Python 3.11+
- WB API токен (из WB Partners)
- Google Service Account с доступом к Sheets
- Supabase проект (для истории тарифов и таблицы КТР/КРП)
```

- [ ] **Step 8.3: Final commit**

```bash
git add README.md
git commit -m "docs: add README with quick start and tool overview"
```

---

## Проверка покрытия спецификации

| Требование из спека | Реализовано |
|--------------------|-------------|
| Новый репо `wb-logistics-toolkit` | ✅ Task 1 |
| `cabinets.yaml` вместо CABINET_1/2 | ✅ Task 1 + Task 3 |
| `warehouse_status.yaml` с флагами и лимитами | ✅ Task 2 |
| `WBClient(token=...)` без зависимостей | ✅ Task 4 |
| `fetch_orders`, `fetch_box_tariffs`, `fetch_warehouse_remains`, `fetch_nm_volumes`, `fetch_report` | ✅ Task 5 |
| `shared/supabase.py` singleton | ✅ Task 6 |
| `get_ktr_krp()` из Supabase с кэшем | ✅ Task 6 |
| `check_setup.py` с 7 проверками | ✅ Task 7 |
| `credentials.json` не попадает в git | ✅ `.gitignore` + Task 7 |
| `README.md` | ✅ Task 8 |

**Следующие планы:**
- [Plan 2](2026-05-06-wb-toolkit-plan2-localization.md) — Оптимизатор ИЛ (Фазы 1-3 + Sheets)
- [Plan 3](2026-05-06-wb-toolkit-plan3-audit.md) — Аудит переплат (Excel + ETL)
- Plan 4 — Документация (TBD, файл будет создан позже)

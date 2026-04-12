# MCP Servers

Индекс всех MCP серверов проекта Wookiee.

## Серверы

| Сервер | Язык | Назначение | Tools | Репозиторий |
|--------|------|-----------|-------|-------------|
| [Wildberries](wildberries/) | TypeScript | Wildberries Marketplace API | 158 | [wildberries-mcp-server](https://github.com/danila-matveev/wildberries-mcp-server) |
| [Ozon](ozon/) | TypeScript | Ozon Seller API (маркетплейс) | 250 | [ozon-mcp-server](https://github.com/danila-matveev/ozon-mcp-server) |
| [Finolog](finolog/) | TypeScript | Finolog API (финансовый учёт) | 79 | [finolog-mcp-server](https://github.com/danila-matveev/finolog-mcp-server) |

## Конфигурация

MCP серверы подключаются через `.mcp.json` в корне проекта:

```json
{
  "mcpServers": {
    "wildberries-ip": {
      "type": "stdio",
      "command": "node",
      "args": ["../wildberries-mcp-server/dist/index.js"],
      "env": {
        "WB_API_TOKEN": "<your-token>"
      }
    },
    "wildberries-ooo": {
      "type": "stdio",
      "command": "node",
      "args": ["../wildberries-mcp-server/dist/index.js"],
      "env": {
        "WB_API_TOKEN": "<your-token>"
      }
    },
    "ozon": {
      "type": "stdio",
      "command": "node",
      "args": ["../ozon-mcp-server/dist/index.js"],
      "env": {
        "OZON_CLIENT_ID": "<your-client-id>",
        "OZON_API_KEY": "<your-api-key>"
      }
    },
    "finolog": {
      "type": "stdio",
      "command": "node",
      "args": ["../finolog-mcp-server/dist/index.js"],
      "env": {
        "FINOLOG_API_TOKEN": "<your-token>"
      }
    }
  }
}
```

> Токены хранятся только в `.mcp.json` (gitignored). Никогда не коммитьте токены в репозиторий.

## Архитектура

Все серверы построены по одной архитектуре:

- **Транспорт:** stdio (по умолчанию) или HTTP (`MCP_TRANSPORT=http`)
- **SDK:** `@modelcontextprotocol/sdk`
- **HTTP клиент:** axios
- **Валидация:** Zod
- **Логирование:** Winston
- **Rate limiting:** встроенный, с retry и exponential backoff

## Локальные расположения

```
~/Desktop/Документы/Cursor/
├── wildberries-mcp-server/    # Отдельный git-репо
├── ozon-mcp-server/           # Отдельный git-репо
├── finolog-mcp-server/        # Отдельный git-репо
└── Wookiee/
    ├── .mcp.json              # Конфигурация подключения
    └── mcp/                   # Документация (эта папка)
        ├── README.md
        ├── wildberries/
        │   ├── README.md
        │   └── api-reference.md
        ├── ozon/
        │   ├── README.md
        │   └── api-reference.md
        └── finolog/
            ├── README.md
            └── api-reference.md
```

# Ozon MCP Server — Design Spec

**Date:** 2026-04-06
**Status:** Draft
**Author:** Claude + Danila

## Overview

MCP-сервер для полного Ozon Seller API (~278 методов, 33 категории). Отдельный GitHub-репозиторий, архитектура 1:1 с существующим `finolog-mcp-server`. Предназначен для использования AI-агентами (Oleg, Ibrahim и др.) через Claude Code / MCP protocol.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Scope | Все ~278 методов Seller API | Полное покрытие для любых агентов |
| Approach | Ручной по паттерну Finolog | Проверенный паттерн, качественные описания тулов |
| Location | `~/Desktop/Документы/Cursor/ozon-mcp-server/` | Рядом с finolog-mcp-server, единообразно |
| Stack | TypeScript 5.7+, Node.js 18+, MCP SDK | Идентично Finolog |
| Transport | stdio (default) + http (optional) | Идентично Finolog |
| Multi-account | ИП (default) + ООО через env | Два набора ключей уже в .env |

## Architecture

```
ozon-mcp-server/
├── src/
│   ├── index.ts                 # Entry point, MCP server setup
│   ├── client/
│   │   ├── ozon-client.ts       # Axios wrapper, Client-Id + Api-Key auth
│   │   ├── auth.ts              # Credential validation & header generation
│   │   ├── rate-limiter.ts      # Rate limiter with 429 backoff
│   │   └── error-handler.ts     # Ozon API error mapping & retry
│   ├── config/
│   │   ├── config.ts            # Base URL, timeouts, rate limits
│   │   └── env.ts               # Zod env validation
│   ├── tools/
│   │   ├── index.ts             # Tool registry (all tools aggregated)
│   │   ├── product/             # ~23 tools
│   │   ├── fbs/                 # ~22 tools
│   │   ├── fbo-supply/          # ~19 tools
│   │   ├── delivery-fbs/        # ~18 tools
│   │   ├── fbo/                 # ~13 tools
│   │   ├── fbs-marks/           # ~13 tools
│   │   ├── pricing-strategy/    # ~12 tools
│   │   ├── certification/       # ~12 tools
│   │   ├── finance/             # ~10 tools
│   │   ├── prices-stocks/       # ~9 tools
│   │   ├── beta/                # ~9 tools
│   │   ├── delivery-rfbs/       # ~8 tools
│   │   ├── return-fbo/          # ~8 tools
│   │   ├── return-rfbs/         # ~8 tools
│   │   ├── report/              # ~8 tools
│   │   ├── premium/             # ~8 tools
│   │   ├── promos/              # ~8 tools
│   │   ├── chat/                # ~8 tools
│   │   ├── qa/                  # ~8 tools
│   │   ├── review/              # ~7 tools
│   │   ├── pass/                # ~7 tools
│   │   ├── cancellation/        # ~7 tools
│   │   ├── category/            # ~6 tools
│   │   ├── barcode/             # ~5 tools
│   │   ├── polygon/             # ~4 tools
│   │   ├── supplier/            # ~4 tools
│   │   ├── digital/             # ~4 tools
│   │   ├── analytics/           # ~2 tools
│   │   ├── warehouse/           # ~2 tools
│   │   ├── quants/              # ~2 tools
│   │   ├── rating/              # ~2 tools
│   │   ├── brand/               # ~1 tool
│   │   └── returns/             # ~1 tool
│   └── utils/
│       ├── logger.ts            # Winston logger
│       ├── response.ts          # Response formatter
│       └── error.ts             # Error formatter
├── package.json
├── tsconfig.json
├── .env.example
├── .gitignore
└── README.md
```

## API Configuration

| Parameter | Value |
|-----------|-------|
| Base URL | `https://api-seller.ozon.ru` |
| Auth Headers | `Client-Id` + `Api-Key` |
| Rate Limiting | Exponential backoff on 429 (no official limits published) |
| Retry | 3 attempts max, 1s initial, 2x multiplier, 10s max |
| Timeout | 30s standard, 120s for file uploads |
| Request format | POST with JSON body (all Ozon endpoints are POST) |

## Environment Variables

```bash
# Required
OZON_CLIENT_ID=1410333          # Default account (ИП)
OZON_API_KEY=<api-key>

# Optional (second account)
OZON_CLIENT_ID_OOO=1540263
OZON_API_KEY_OOO=<api-key>

# Optional
MCP_TRANSPORT=stdio              # stdio | http
MCP_PORT=8082                    # Only for http transport
LOG_LEVEL=info                   # debug | info | warn | error
```

## Tool Pattern

Each tool follows the Finolog pattern — one file per operation:

```typescript
// src/tools/product/list.ts
import { ToolDefinition, ToolHandler } from '../../types';

export const productListTool: ToolDefinition = {
  name: 'ozon_product_list',
  description: 'Get list of products with pagination. Returns product_id, offer_id, and basic info.',
  inputSchema: {
    type: 'object',
    properties: {
      filter: {
        type: 'object',
        description: 'Filter criteria',
        properties: {
          offer_id: { type: 'array', items: { type: 'string' }, description: 'Filter by seller SKU' },
          product_id: { type: 'array', items: { type: 'number' }, description: 'Filter by product ID' },
          visibility: { type: 'string', enum: ['ALL', 'VISIBLE', 'INVISIBLE', 'EMPTY_STOCK', 'NOT_MODERATED', 'MODERATED', 'DISABLED', 'STATE_FAILED', 'READY_TO_SUPPLY', 'VALIDATION_STATE_PENDING', 'VALIDATION_STATE_FAIL', 'VALIDATION_STATE_SUCCESS', 'TO_SUPPLY', 'IN_SALE', 'REMOVED_FROM_SALE', 'BAN_NOT_SKU', 'ARCHIVED', 'OVERPRICED'] }
        }
      },
      last_id: { type: 'string', description: 'Last product ID for pagination' },
      limit: { type: 'number', description: 'Number of products per page (max 1000)', default: 100 }
    }
  }
};

export const productListHandler: ToolHandler = async (params, client) => {
  return client.post('/v2/product/list', params);
};
```

## Tool Naming Convention

All tools prefixed with `ozon_` + domain + operation:
- `ozon_product_list`
- `ozon_product_info`
- `ozon_fbs_posting_list`
- `ozon_finance_transaction_list`
- `ozon_analytics_data`

## 33 Tool Categories

| # | Domain | Folder | ~Methods | Key Endpoints |
|---|--------|--------|----------|---------------|
| 1 | Product | `product/` | 23 | list, info, import, update, archive, delete, attributes |
| 2 | FBS | `fbs/` | 22 | posting list/get/ship, cancel, labels, tracking |
| 3 | FBO Supply | `fbo-supply/` | 19 | supply request CRUD, timeslots |
| 4 | Delivery FBS | `delivery-fbs/` | 18 | delivery methods, tracking number set |
| 5 | FBO | `fbo/` | 13 | posting list/get, shipment info |
| 6 | FBS Marks | `fbs-marks/` | 13 | labeling, packaging marks |
| 7 | Pricing Strategy | `pricing-strategy/` | 12 | strategy CRUD, competitor prices |
| 8 | Certification | `certification/` | 12 | quality certificates, brand docs |
| 9 | Finance | `finance/` | 10 | transactions, realization, totals |
| 10 | Prices & Stocks | `prices-stocks/` | 9 | stock update, price import, info |
| 11 | Beta | `beta/` | 9 | experimental endpoints |
| 12 | Delivery rFBS | `delivery-rfbs/` | 8 | rFBS delivery methods |
| 13 | Return FBO | `return-fbo/` | 8 | FBO return processing |
| 14 | Return rFBS | `return-rfbs/` | 8 | rFBS return management |
| 15 | Report | `report/` | 8 | report create/status/download |
| 16 | Premium | `premium/` | 8 | premium seller features |
| 17 | Promos | `promos/` | 8 | promotions, actions |
| 18 | Chat | `chat/` | 8 | messages, chat list/history |
| 19 | Q&A | `qa/` | 8 | questions & answers |
| 20 | Review | `review/` | 7 | review list/management |
| 21 | Pass | `pass/` | 7 | warehouse delivery passes |
| 22 | Cancellation | `cancellation/` | 7 | order cancellation requests |
| 23 | Category | `category/` | 6 | category tree, attributes, values |
| 24 | Barcode | `barcode/` | 5 | barcode generation |
| 25 | Polygon | `polygon/` | 4 | delivery zone polygons |
| 26 | Supplier | `supplier/` | 4 | supplier info |
| 27 | Digital | `digital/` | 4 | digital product management |
| 28 | Analytics | `analytics/` | 2 | analytics data, reports |
| 29 | Warehouse | `warehouse/` | 2 | warehouse list/info |
| 30 | Quants | `quants/` | 2 | economy segment products |
| 31 | Seller Rating | `rating/` | 2 | rating summary/history |
| 32 | Brand | `brand/` | 1 | brand certificate |
| 33 | Returns List | `returns/` | 1 | return shipment lists |

**Total: ~278 tools**

## Implementation Workflow (Multi-Agent)

### Agent 1 — Researcher
- Parses all Ozon Seller API documentation pages
- Produces `docs/api-catalog.json` — complete registry of all ~278 methods
- Each entry: `{ path, httpMethod, description, parameters, responseSchema, apiVersion }`

### Agent 2 — Builder
- Receives catalog from Agent 1
- Creates project skeleton: package.json, tsconfig, client, config, utils
- Implements all 278 tools organized by category folders
- Each tool: definition (name, description, inputSchema) + handler (API call)

### Agent 3 — Tester
- Tests each category with real API keys (ИП account)
- Validates: auth, rate limiting, error handling, response parsing
- Produces test report, applies fixes

### Agent 4 — Project Manager (Coordinator)
- Orchestrates: Agent 1 → Agent 2 → Agent 3
- Reviews output of each agent before passing to next
- Finalizes: README, .env.example, .mcp.json registration

### Execution Order
```
Agent 1 (Research) → Agent 4 (Review) → Agent 2 (Build) → Agent 4 (Review) → Agent 3 (Test) → Agent 4 (Finalize)
```

## Registration

After build, register in Wookiee project:

```json
// .mcp.json
{
  "mcpServers": {
    "ozon": {
      "type": "stdio",
      "command": "node",
      "args": ["../ozon-mcp-server/dist/index.js"],
      "env": {
        "OZON_CLIENT_ID": "<client-id>",
        "OZON_API_KEY": "<api-key>"
      }
    }
  }
}
```

## Success Criteria

1. All ~278 Ozon Seller API methods available as MCP tools
2. Auth works with both ИП and ООО accounts
3. Rate limiting with 429 backoff handles Ozon throttling
4. Error messages are clear and actionable for AI agents
5. README with full tool catalog and setup instructions
6. Registered in Wookiee .mcp.json and working with Claude Code
7. Separate GitHub repository at `ozon-mcp-server`

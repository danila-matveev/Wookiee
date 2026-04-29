# Notion Formatting Guide for Monthly Plans

## Table Format

Use Notion-native tables instead of markdown:

```html
<table fit-page-width="true" header-row="true" header-column="true">
<tr color="blue_bg">
<td>Показатель</td>
<td>WB Март, тыс.₽</td>
<td>OZON Март, тыс.₽</td>
</tr>
<tr>
<td>Выручка</td>
<td>36 482</td>
<td>6 595</td>
</tr>
<tr color="gray_bg">
<td>**ИТОГО**</td>
<td>**43 077**</td>
<td>**—**</td>
</tr>
</table>
```

## Row Colors

| Color | Usage |
|---|---|
| `blue_bg` | Header rows |
| `gray_bg` | Total/summary rows |
| `green_bg` | Positive highlight rows |
| `red_bg` | Negative/warning rows |
| `purple_bg` | Strategic decision rows |

## Cell Colors

| Color | Usage |
|---|---|
| `green_bg` | Positive values (ROAS >30x, growth >20%, OK status) |
| `red_bg` | Negative values (losses, УБЫТОК, ДЕФИЦИТ, МЁРТВЫЙ СТОК) |
| `yellow_bg` | Warning values (ВНИМАНИЕ, FREEZE, OVERSTOCK) |

## Callout Blocks

```html
<callout icon="📊" color="blue_bg">
	Section summary — key numbers.
</callout>

<callout icon="💡" color="green_bg">
	Positive insight or recommendation.
</callout>

<callout icon="⚠️" color="yellow_bg">
	Data quality note or warning.
</callout>

<callout icon="🚨" color="red_bg">
	URGENT action required.
</callout>

<callout icon="🔥" color="purple_bg">
	Strategic decision or new initiative.
</callout>
```

## Toggle Headers

**ALL headings at every level must be toggle headings in Notion:**

- `##` (H2) → Toggle Heading 1 — main sections (0-6 + Справочно)
- `###` (H3) → Toggle Heading 2 — subsections (Разбивка по каналам, Обоснование, Сценарии)
- `####` (H4) → Toggle Heading 3 — details (per-model rationale, fact tables)

Every section is collapsible. The "Справочно" section should be collapsed by default in Notion.

Toggle headings allow the reader to:
1. See the full document outline (all sections collapsed)
2. Expand only the sections they need
3. Navigate quickly to any section

## Plan vs Fact Parity

The plan P&L table (Section 2) must have the same detail level as the fact P&L in Reference. Both should have the full waterfall: Revenue, SPP, COGS, logistics, storage, commission, NDS, ads, margin.

Single margin throughout — no M-1/M-2 distinction in any table.

## Header Rules

- All table headers must be human-readable in Russian
- NO abbreviations: "Выручка WB, тыс.₽" not "WB Rev,К"
- Units always explicit: тыс.₽, %, шт, дн

## When to Add Callouts

- After Section 0 (key metrics highlight)
- After Section 1 (urgent inventory actions)
- After Section 4 (top recommendation summary)
- After Section 5 (ad budget decision)
- After Верификация in Справочно (quality summary)

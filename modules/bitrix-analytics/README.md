# bitrix-analytics

Weekly team activity analytics from Bitrix24. Collects tasks and chat messages, generates a structured report.

## How it works

1. `fetch_data.py` pulls tasks and chat messages from Bitrix24 REST API
2. Saves raw data to `/tmp/bitrix_report_data.json`
3. Claude (via SKILL.md) reads the JSON and generates a human-readable report
4. Report is saved to `reports/YYYY-MM-DD.md`

## Usage

```bash
# Collect data for the last 7 days (default)
python3 fetch_data.py

# Collect data for a custom period
python3 fetch_data.py --days 14

# Save to a custom path
python3 fetch_data.py --days 7 --output /tmp/custom_output.json
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `Bitrix_rest_api` | Bitrix24 REST API webhook URL (from root `.env`) |

## Dependencies

- Python 3.8+
- `python-dotenv` (for reading `.env`)
- All other imports are stdlib (`urllib`, `json`, `argparse`, `os`, `datetime`)

## Files

- `config.py` — staff mapping, departments, excluded IDs, key group chats
- `fetch_data.py` — data collection script
- `reports/` — generated reports (YYYY-MM-DD.md)

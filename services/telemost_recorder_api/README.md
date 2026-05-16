# Telemost Recorder API

FastAPI service for the Wookiee meeting recorder. It receives Telegram webhook
updates, syncs allowed users from Bitrix24, queues Yandex Telemost meetings for
recording, and sends summaries/transcripts back to users.

## Entrypoints

```bash
# Local health app
uvicorn services.telemost_recorder_api.app:create_app --factory --host 0.0.0.0 --port 8006

# One-shot Telegram bot setup
python -m scripts.telemost_setup_webhook \
  --webhook-url https://recorder.os.wookiee.shop/telegram/webhook
```

## Runtime Notes

- `deploy/Dockerfile.telemost_recorder_api` builds the production container.
- The service spawns `telemost_recorder` containers through the mounted Docker
  socket for individual recordings.
- `services/telemost_recorder_api/assets/avatar.png` is an intentional tracked
  asset used by `scripts.telemost_setup_webhook` when the bot has no avatar.
- Secrets stay in `.env` / GitHub Actions secrets only.

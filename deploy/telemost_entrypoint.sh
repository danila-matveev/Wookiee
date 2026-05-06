#!/bin/bash
set -e
# Start PulseAudio in background (daemon mode)
pulseaudio --start --exit-idle-time=-1 --daemon 2>/dev/null || true
# Launch whatever command was passed
exec "$@"

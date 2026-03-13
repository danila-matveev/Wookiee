"""Run Dashboard API with: python -m services.dashboard_api"""
import uvicorn

from services.dashboard_api.app import app

uvicorn.run(app, host="0.0.0.0", port=8001)

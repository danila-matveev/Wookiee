"""
Knowledge Base service entrypoint.

Usage:
    python -m services.knowledge_base          # Run API server
    python -m services.knowledge_base --port 8002
"""

import argparse
import logging
import os


def main():
    parser = argparse.ArgumentParser(description="Knowledge Base API Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.getenv("KB_PORT", "8002")))
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    import uvicorn
    uvicorn.run(
        "services.knowledge_base.app:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
    )


if __name__ == "__main__":
    main()

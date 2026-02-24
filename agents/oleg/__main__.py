"""Allow running as: python -m agents.oleg"""
import asyncio
import sys


def main():
    from agents.oleg.app import OlegApp
    app = OlegApp()
    asyncio.run(app.run())


if __name__ == "__main__":
    main()

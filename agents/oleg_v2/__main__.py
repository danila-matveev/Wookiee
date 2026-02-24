"""Allow running as: python -m agents.oleg_v2"""
import asyncio
import sys


def main():
    from agents.oleg_v2.app import OlegApp
    app = OlegApp()
    asyncio.run(app.run())


if __name__ == "__main__":
    main()

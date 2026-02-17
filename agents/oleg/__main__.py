"""Allow running as: python -m agents.oleg [bot|agent]"""
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else "bot"

if mode == "agent":
    from agents.oleg.agent_runner import main
else:
    from agents.oleg.main import main

main()

"""One-click E2E: installs frontend deps, then runs the Playwright suite.

Run it from PyCharm: right-click -> Run 'run_e2e'. No terminal needed.
(Requires the API venv to be named .venv at the project root, and
Playwright browsers installed: npx playwright install chromium)
"""

import subprocess
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent / "frontend"


def run(*cmd):
    print(f"$ {' '.join(cmd)}", flush=True)
    subprocess.run(list(cmd), cwd=FRONTEND, check=True)


run("npm.cmd", "install")
run("npx.cmd", "playwright", "test")
print("DONE")

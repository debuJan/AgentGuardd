"""Start the AgentGuard API for local development.

Usage (PyCharm terminal, project root):
    .\\.venv\\Scripts\\python start_api.py

Wait for "Uvicorn running on http://127.0.0.1:8000", then start the
dashboard (see START_HERE.txt). Stop with Ctrl+C.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.api.app:app", host="127.0.0.1", port=8000)

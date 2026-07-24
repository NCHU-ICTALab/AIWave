"""啟動題組對話測試伺服器：`uv run main.py`，再開 http://localhost:8000"""

import uvicorn


def main() -> None:
    uvicorn.run("api.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()

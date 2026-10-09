"""启动第一阶段订票 Agent API。"""

import os
import sys
from pathlib import Path

# 允许直接运行 `python scripts/run_api.py` 时导入项目根目录下的 app 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8010")),
        reload=False,
    )

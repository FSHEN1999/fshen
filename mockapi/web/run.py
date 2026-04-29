# -*- coding: utf-8 -*-
"""uvicorn 启动脚本 - 运行 python web/run.py 启动应用"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(Path(__file__).parent)],
    )

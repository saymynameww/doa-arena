"""启动后端服务脚本。"""

import logging
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
logger.info("正在启动 Arena Web 服务...")

# 创建应用
from packages.arena.src.arena.server.app import create_app

app = create_app()

# 启动服务
logger.info("服务将在 http://127.0.0.1:8765 启动")
logger.info("按 Ctrl+C 停止服务")

uvicorn.run(
    app,
    host="127.0.0.1",
    port=8765,
    log_level="info",
)

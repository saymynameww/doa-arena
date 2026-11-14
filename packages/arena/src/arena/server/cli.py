"""Web 服务命令行入口。"""

import logging


def main() -> None:
    """启动 Web 服务。"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("正在启动 Arena Web 服务...")

    # 导入 uvicorn
    try:
        import uvicorn
    except ImportError:
        logger.error("uvicorn 未安装。请运行: pip install uvicorn")
        return

    # 创建应用
    from .app import create_app

    app = create_app()

    # 启动服务
    logger.info("服务将在 http://127.0.0.1:8765 启动")
    uvicorn.run(
        app,
        host="127.0.0.1",  # 只监听本地（安全）
        port=8765,
        log_level="info",
    )


if __name__ == "__main__":
    main()

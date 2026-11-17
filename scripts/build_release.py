"""构建并打包本地 Web 产品；不上传任何发布平台。"""

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """将前端构建产物放入 Python wheel，运行时无需 Node。"""
    root = Path(__file__).resolve().parents[1]
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        raise SystemExit("构建需要 Node/npm，请先安装；安装包的使用者无需 Node。")
    subprocess.run([npm, "run", "build"], cwd=root / "frontend", check=True)
    target = root / "packages/arena/src/arena/server/static"
    # 只清理这个脚本生成的目录，防止旧哈希资源进入新安装包。
    if target.exists():
        if target.resolve().parent != (root / "packages/arena/src/arena/server").resolve():
            raise RuntimeError("静态目录位置异常，请检查路径")
        shutil.rmtree(target)
    shutil.copytree(root / "frontend/dist", target)
    # setuptools 会复用 build/lib；清掉旧构建以免带入上次的哈希资源。
    build = root / "packages/arena/build"
    if build.exists():
        if build.resolve().parent != (root / "packages/arena").resolve():
            raise RuntimeError("构建目录位置异常，请检查路径")
        shutil.rmtree(build)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            str(root / "packages/arena"),
            "--wheel-dir",
            str(root / "dist"),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()

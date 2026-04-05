# -*- coding: utf-8 -*-
"""
YOLO模型管理器

负责从 ptcgp-assets 仓库下载和管理YOLO模型，提供全局单例访问。
"""

import logging
import os
import platform
import threading
from pathlib import Path
from typing import Optional

import requests

# YOLO导入延迟到实际使用时，避免启动时加载
YOLO = None

logger = logging.getLogger(__name__)

ASSETS_REPO = "shelken/ptcgp-assets"
# 使用 jsDelivr CDN 加速下载，避免 GitHub 速率限制
MODELS_BASE_URL = f"https://cdn.jsdelivr.net/gh/{ASSETS_REPO}@main/models"
# GitHub API 用于获取目录内容
GITHUB_API_URL = f"https://api.github.com/repos/{ASSETS_REPO}/contents"

# 模型配置
MODEL_SUBDIR = "yolo11n-10k-100-2026.02.08"
# MODEL_SUBDIR = "yolo11n-5k-25-2026.02.02"
# MODEL_SUBDIR = "yolo26s-10k-50-2026.02.06" # 识别降低
MODEL_NAME = "best"  # best.pt 或 best.mlpackage


class ModelManager:
    """YOLO模型管理器"""

    def __init__(self, models_dir: str = "data/models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._model: Optional["YOLO"] = None  # type: ignore
        self._model_ready = threading.Event()
        self._lock = threading.Lock()
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        )

    def _is_macos(self) -> bool:
        """检查是否为 macOS 系统"""
        return platform.system() == "Darwin"

    def get_model_path(self) -> Path:
        """获取本地模型路径"""
        if self._is_macos():
            # macOS: best.mlpackage 是一个目录
            return self.models_dir / MODEL_SUBDIR / f"{MODEL_NAME}.mlpackage"
        else:
            # 其他平台: best.pt 是一个文件
            return self.models_dir / MODEL_SUBDIR / f"{MODEL_NAME}.pt"

    def _download_file(self, url: str, local_path: Path) -> bool:
        """下载单个文件"""
        try:
            response = self._session.get(url, stream=True, timeout=120)
            response.raise_for_status()

            # 确保目录存在
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # 获取文件大小用于进度显示
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and downloaded % (1024 * 1024) == 0:
                            progress = (downloaded / total_size) * 100
                            logger.debug(f"下载进度: {progress:.1f}%")

            return True
        except Exception as e:
            logger.error(f"下载文件失败 {url}: {e}")
            if local_path.exists():
                local_path.unlink()
            return False

    def _download_directory(self, api_path: str, local_dir: Path) -> bool:
        """
        递归下载 GitHub 仓库中的目录

        Args:
            api_path: API 路径（如 models/yolo11n-5k-25-2026.02.02/best.mlpackage）
            local_dir: 本地保存目录
        """
        try:
            # 获取目录内容
            url = f"{GITHUB_API_URL}/{api_path}?ref=main"
            response = self._session.get(url, timeout=30)
            response.raise_for_status()
            items = response.json()

            if not isinstance(items, list):
                logger.error(f"API 返回格式错误: {url}")
                return False

            success = True
            for item in items:
                item_name = item["name"]
                item_type = item["type"]
                item_path = item["path"]

                local_item_path = local_dir / item_name

                if item_type == "file":
                    # 下载文件
                    download_url = item["download_url"]
                    if not download_url:
                        logger.warning(f"文件没有下载链接: {item_path}")
                        continue

                    logger.debug(f"下载文件: {item_name}")
                    if not self._download_file(download_url, local_item_path):
                        success = False

                elif item_type == "dir":
                    # 递归下载子目录
                    if not self._download_directory(item_path, local_item_path):
                        success = False

            return success

        except Exception as e:
            logger.error(f"下载目录失败 {api_path}: {e}")
            return False

    def download_model(self, force: bool = False) -> bool:
        """从ptcgp-assets下载模型"""
        model_path = self.get_model_path()

        if model_path.exists() and not force:
            logger.debug(f"模型已存在: {model_path}")
            return True

        if self._is_macos():
            # macOS: 下载 best.mlpackage 目录
            logger.info("正在下载 CoreML 模型目录...")
            api_path = f"models/{MODEL_SUBDIR}/best.mlpackage"
            return self._download_directory(api_path, model_path)
        else:
            # 其他平台: 下载 best.pt 文件
            logger.info("正在下载 PyTorch 模型文件...")
            url = f"{MODELS_BASE_URL}/{MODEL_SUBDIR}/best.pt"
            return self._download_file(url, model_path)

    def load_model_async(self):
        """后台线程异步加载模型"""

        def _load():
            try:
                # 降低 coremltools 日志噪音（避免输出 Registering op ...）
                for name in [
                    "coremltools",
                    "coremltools.converters",
                    "coremltools.converters.mil",
                    "coremltools.converters.mil.mil",
                    "coremltools.converters.mil.mil.ops",
                ]:
                    logging.getLogger(name).setLevel(logging.WARNING)

                # 延迟导入YOLO，避免启动时加载
                global YOLO
                if YOLO is None:
                    # 依赖由项目环境统一管理，必须在首次导入 ultralytics 前强制关闭运行时自动装包。
                    os.environ["YOLO_AUTOINSTALL"] = "false"
                    os.environ["ULTRALYTICS_SKIP_REQUIREMENTS_CHECKS"] = "1"
                    from ultralytics import YOLO as _YOLO

                    YOLO = _YOLO

                model_path = self.get_model_path()

                # 1. 确保模型已下载
                if not model_path.exists():
                    logger.info("模型不存在，开始下载...")
                    if not self.download_model():
                        logger.error("模型下载失败，无法加载")
                        return

                # 2. 加载模型（显式指定 OBB 任务，避免 CoreML 无法自动识别）
                logger.info(f"正在加载YOLO模型: {model_path}")
                with self._lock:
                    self._model = YOLO(str(model_path), task="obb")
                    self._model_ready.set()

                logger.info("YOLO模型加载完成，识别功能已就绪")

            except Exception as e:
                logger.error(f"加载模型失败: {e}", exc_info=True)

        # 启动后台线程加载模型
        thread = threading.Thread(target=_load, daemon=True, name="ModelLoader")
        thread.start()
        logger.debug("模型加载线程已启动")

    def is_model_ready(self) -> bool:
        """检查模型是否加载完成"""
        return self._model_ready.is_set()

    def wait_for_model(self, timeout: Optional[float] = None) -> bool:
        """
        等待模型加载完成

        Args:
            timeout: 超时时间（秒），None表示无限等待

        Returns:
            True表示模型加载完成，False表示超时
        """
        return self._model_ready.wait(timeout=timeout)

    def get_model(self) -> Optional["YOLO"]:  # type: ignore
        """获取已加载的模型"""
        with self._lock:
            return self._model


# 全局单例实例
_model_manager_instance: Optional[ModelManager] = None
_model_manager_lock = threading.Lock()


def get_model_manager() -> ModelManager:
    """
    获取全局模型管理器单例

    使用双重检查锁定确保线程安全。

    Returns:
        ModelManager单例实例
    """
    global _model_manager_instance

    if _model_manager_instance is None:
        with _model_manager_lock:
            if _model_manager_instance is None:
                _model_manager_instance = ModelManager()

    return _model_manager_instance

# YOLO+感知哈希替换模板匹配卡牌识别 实施计划

> **目标**: 使用YOLO检测+感知哈希匹配替换现有的模板匹配方式识别开包结果卡牌
> **范围**: 修改 `open_pack.py` 中的 `_recognize_cards()` 方法，实现新的卡牌扫描流程
> **技术要求**:
> - 启动时异步加载YOLO模型
> - 内存Hash匹配（Dict结构）
> - 扫描前确保目标系列所有卡牌都有Hash值
> - 从 `shelken/ptcgp-assets` 仓库下载模型和卡牌图片
>
> **新增依赖**: `ultralytics>=8.3.0`, `scipy>=1.17.0`

---

## 关键设计决策

### 1. 模型管理策略

**模型来源**: `shelken/ptcgp-assets` 仓库 `models/` 目录
- macOS使用 `.mlpackage` (CoreML格式)
- 其他平台使用 `.pt` (PyTorch格式)
- 下载后放入 `data/models/` 目录

**加载策略**: 启动时异步加载 + 全局单例模式
- `main_v2.py` 启动时创建后台线程加载模型
- 模型加载完成前，YOLO识别功能不可用（但其他任务正常）
- 加载完成后通过 Event/标志位通知

**注入路径**（方案1：全局单例）：
```python
# src/ptcgp_auto_v2/infra/model_manager.py
_model_manager: Optional[ModelManager] = None

def get_model_manager() -> ModelManager:
    """获取全局模型管理器单例"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager

# src/ptcgp_auto_v2/main.py 启动时
from ptcgp_auto_v2.infra.model_manager import get_model_manager
model_manager = get_model_manager()
model_manager.load_model_async()  # 后台加载

# OpenPackTask 使用时
from ptcgp_auto_v2.infra.model_manager import get_model_manager
self.model_manager = get_model_manager()
if not self.model_manager.is_model_ready():
    # 等待或跳过
    pass
```
此方案改动最小，无需修改 Executor/Task 架构。

### 2. Hash匹配策略（内存匹配）

**数据结构**:
```python
# 按系列索引（开包识别用）
_series_cache: Dict[str, Dict[int, np.ndarray]]  # {set_code: {number: hash}}

# 全局索引（跨系列检测用）
_global_cache: Dict[str, np.ndarray]  # key: "A1/001", value: hash
```

**加载模式**:
1. **单系列模式**: `load_series_hash(set_code)` - 加载指定系列，用于开包识别
2. **全局模式**: `load_all_hashes()` - 加载所有系列，用于跨系列卡牌检测

**匹配接口**:
```python
# 系列内匹配（开包用）
def find_best_match(
    self, 
    target_hash: np.ndarray,
    set_code: str,  # 指定系列
    threshold: float = 0.8
) -> Optional[Tuple[int, float]]:
    """返回: (card_number, similarity)"""

# 全局匹配（跨系列检测用）
def find_best_match_globally(
    self,
    target_hash: np.ndarray,
    threshold: float = 0.8
) -> Optional[Tuple[str, int, float]]:
    """返回: (set_code, card_number, similarity)"""
```

**匹配算法**: 汉明距离计算
```python
def calculate_similarity(hash1, hash2) -> float:
    diff = hash1 ^ hash2
    distance = sum(x.bit_count() for x in diff)
    return 1.0 - distance / total_bits
```

### 3. Hash缺失处理策略（扫描前批量确保）

**流程**:
1. 开包流程开始前，确定目标系列 `set_code`
2. 查询该系列所有卡牌，检查 `perceptual_hash` 字段
3. 找出缺失hash的卡牌列表，**过滤掉已下载失败的（内存缓存）**
4. 并发下载这些卡牌的图片（从 `ptcgp-assets`）
5. 计算hash并更新数据库，**下载失败的记录到内存缓存**
6. 所有hash就绪后，才开始扫描识别

**防重复下载机制（内存缓存）**:
- 使用 `self._failed_downloads: Set[str]` 记录下载失败的卡牌
- 格式: `"{set_code}/{number:03d}"`（如 "A1/001"）
- **按卡牌粒度记录**：每张卡牌独立标记，不影响同系列其他卡牌
- **本次运行有效**：重启后清空缓存，会再次尝试（允许远程仓库补充缺失卡牌）
- **强制刷新接口**：`clear_failed_cache(set_code=None)` 可手动清空缓存重新下载

**下载来源**: 
- jsDelivr CDN: `https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/images/zh-TW/cards-by-set/{set_code}/{number}.png`
- 备注：当前实现仅使用 jsDelivr CDN（未接入 GitHub Raw 备用源）

### 4. 数据库表结构修改

**Card表新增字段**:
```python
perceptual_hash: Optional[str] = Field(default=None, description="感知哈希值(Base64编码)")
```

### 5. 核心类设计

**YoloCardRecognizer** (`src/ptcgp_auto_v2/infra/yolo_card_recognizer.py`):
- `scan_pack_result()`: 扫描开包结果页，返回识别到的卡牌列表
- `detect_cards()`: YOLO检测并裁剪卡牌图片
- `match_cards()`: 使用hash匹配识别卡牌

**CardHashManager** (`src/ptcgp_auto_v2/infra/card_hash_manager.py`):
- `ensure_series_ready(set_code)`: 确保某系列所有卡牌都有hash（下载缺失图片并计算，使用内存缓存避免重复下载）
- `load_series_hash(set_code)`: 加载某系列hash到内存（系列模式）
- `load_all_hashes()`: 加载所有系列hash到内存（全局模式）
- `find_best_match(target_hash, set_code=None, threshold=0.8)`: 查找最佳匹配
  - `set_code`指定时: 返回 `(card_number, similarity)`
  - `set_code=None`时: 返回 `(set_code, card_number, similarity)`（跨系列匹配）
- `clear_failed_cache(set_code=None)`: 清空下载失败缓存（强制刷新用）
- `get_failed_count(set_code=None)`: 获取下载失败的卡牌数量

**ModelManager** (`src/ptcgp_auto_v2/infra/model_manager.py`):
- `download_model()`: 从ptcgp-assets下载模型
- `load_model_async()`: 异步加载模型
- `is_model_ready()`: 检查模型是否加载完成

---

## 实施任务清单

### 阶段1: 基础设施搭建（预计 2-3 小时）

#### Task 1.1: 数据库模型修改
**文件**: `src/ptcgp_auto_v2/db/models/card.py`
**操作**: 
- 在 `Card` 模型新增 `perceptual_hash` 字段
- 类型: `Optional[str]`, 默认 None
- 描述: 感知哈希值的Base64编码

**验证**: 
```python
# 测试字段存在
card = Card(set_code="A1", number=1, name="Test", rarity="C", image_url="url")
assert hasattr(card, 'perceptual_hash')
assert card.perceptual_hash is None
```

---

#### Task 1.2: 数据库迁移脚本（增强版）
**文件**: `scripts/migration_add_hash_field.py` (新建)
**功能**:
1. 为现有Card表添加 `perceptual_hash` 列
2. **利用本地已有卡牌图片预填充数据库**（避免重复下载）

**代码模板**:
```python
#!/usr/bin/env python3
"""
数据库迁移脚本：添加 perceptual_hash 字段并预填充数据
利用 yolo-card-training/data/raw/cards/ 目录下的现有图片
"""

import sys
from pathlib import Path
from sqlalchemy import text
from PIL import Image
from tqdm import tqdm

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.utils.perceptual_hash import (
    pil_to_color_pixels,
    calculate_perceptual_hash,
    encode_hash_to_base64,
)

# 本地卡牌图片目录（yolo-card-training项目中的图片）
LOCAL_CARDS_DIR = Path("yolo-card-training/data/raw/cards")


def add_hash_column():
    """添加 perceptual_hash 字段到 Card 表"""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE cards ADD COLUMN perceptual_hash VARCHAR(255)"
        ))
        conn.commit()
    print("✅ 已添加 perceptual_hash 字段")


def fill_hash_from_local_images():
    """利用本地图片预填充 perceptual_hash"""
    repo = CardRepository()
    
    if not LOCAL_CARDS_DIR.exists():
        print(f"⚠️ 本地卡牌目录不存在: {LOCAL_CARDS_DIR}")
        print("跳过预填充，将在首次扫描时自动下载")
        return 0, 0
    
    print(f"📂 扫描本地卡牌目录: {LOCAL_CARDS_DIR}")
    
    total_processed = 0
    total_success = 0
    
    # 遍历所有系列目录
    set_dirs = [d for d in LOCAL_CARDS_DIR.iterdir() if d.is_dir()]
    
    for set_dir in tqdm(sorted(set_dirs), desc="处理系列"):
        set_code = set_dir.name
        
        # 查找该系列下的所有卡牌图片
        card_files = []
        for ext in [".webp", ".png", ".jpg"]:
            card_files.extend(set_dir.glob(f"*{ext}"))
        
        set_success = 0
        for card_file in sorted(card_files):
            try:
                # 从文件名提取卡牌编号（如 "001.webp" -> 1）
                card_number = int(card_file.stem)
                
                # 查找数据库中对应的卡牌
                card = repo.get_card_by_set_and_number(set_code, card_number)
                if not card:
                    continue
                
                # 如果已有hash，跳过
                if card.perceptual_hash:
                    continue
                
                # 读取图片并计算hash
                pil_img = Image.open(card_file)
                color_pixels = pil_to_color_pixels(pil_img)
                hash_arr = calculate_perceptual_hash(color_pixels)
                hash_str = encode_hash_to_base64(hash_arr)
                
                # 更新数据库
                if repo.update_card_hash(card.id, hash_str):
                    set_success += 1
                    total_success += 1
                
                total_processed += 1
                
            except Exception as e:
                # 静默跳过错误（文件名不符合格式或计算失败）
                pass
        
        if set_success > 0:
            print(f"  ✅ {set_code}: 成功填充 {set_success} 张卡牌")
    
    return total_processed, total_success


def main():
    print("=" * 60)
    print("数据库迁移：添加 perceptual_hash 字段")
    print("=" * 60)
    
    # 1. 添加字段
    add_hash_column()
    
    # 2. 预填充数据
    print("\n🔄 开始预填充 perceptual_hash 数据...")
    processed, success = fill_hash_from_local_images()
    
    print("\n" + "=" * 60)
    print("迁移完成")
    print("=" * 60)
    print(f"  处理卡牌: {processed} 张")
    print(f"  成功填充: {success} 张")
    print(f"\n💡 提示：未填充的卡牌将在首次扫描时自动下载")


if __name__ == "__main__":
    main()
```

**说明**:
- 利用 `yolo-card-training/data/raw/cards/` 目录下已有的卡牌图片
- 遍历所有系列子目录，读取每张图片计算 perceptual hash
- 自动匹配数据库中的卡牌记录并更新 `perceptual_hash` 字段
- 如果本地目录不存在，跳过预填充（将在首次扫描时自动下载）
- 使用 `tqdm` 显示进度条

---

#### Task 1.3: CardRepository扩展
**文件**: `src/ptcgp_auto_v2/db/repositories/card_repository.py`
**新增方法**:
1. `get_cards_without_hash(set_code: str) -> List[Card]`: 获取某系列缺少hash的卡牌
2. `update_card_hash(card_id: int, hash_value: str) -> bool`: 更新卡牌hash值
3. `get_cards_with_hash_by_set(set_code: str) -> Dict[int, str]`: 获取某系列所有有hash的卡牌

**代码模板**:
```python
def get_cards_without_hash(self, set_code: str) -> List[Card]:
    """获取某系列缺少感知哈希的卡牌"""
    with Session(get_engine()) as session:
        statement = select(Card).where(
            Card.set_code == set_code,
            Card.perceptual_hash.is_(None)
        )
        return list(session.exec(statement).all())

def update_card_hash(self, card_id: int, hash_value: str) -> bool:
    """更新卡牌感知哈希值"""
    with Session(get_engine()) as session:
        card = session.get(Card, card_id)
        if not card:
            return False
        card.perceptual_hash = hash_value
        card.updated_at = datetime.now()
        session.add(card)
        session.commit()
        return True

def get_cards_with_hash_by_set(self, set_code: str) -> Dict[int, str]:
    """获取某系列所有有hash的卡牌 {number: hash}"""
    with Session(get_engine()) as session:
        statement = select(Card).where(
            Card.set_code == set_code,
            Card.perceptual_hash.is_not(None)
        )
        cards = session.exec(statement).all()
        return {card.number: card.perceptual_hash for card in cards}
```

---

#### Task 1.4: 感知哈希工具模块
**文件**: `src/ptcgp_auto_v2/utils/perceptual_hash.py` (新建)
**内容**: 从 `test_yolo_hash_match.py` 移植核心函数，使用 scipy 加速 DCT

**函数清单**:
- `pil_to_color_pixels(pil_image: Image) -> ColorPixels`: PIL图片转颜色像素（使用 Image.Resampling.BICUBIC）
- `bgr_to_color_pixels(bgr_image: np.ndarray) -> ColorPixels`: BGR图片转颜色像素（使用 cv2.INTER_CUBIC）
- `calculate_perceptual_hash(color_pixels: ColorPixels) -> np.ndarray`: 计算感知哈希，返回 uint32 数组（189位哈希）
- `calculate_similarity(hash1: np.ndarray, hash2: np.ndarray) -> float`: 计算相似度（汉明距离）
- `encode_hash_to_base64(hash_arr: np.ndarray) -> str`: 哈希转Base64
- `decode_hash_from_base64(encoded: str) -> np.ndarray`: Base64转哈希

**常量**:
- `HASH_SIZE = 96`
- `FREQ_SIZE = 8`

**DCT 实现**: 使用 `scipy.fftpack.dct`（Type II），比纯 Python 实现快 **100-1000 倍**

**依赖**: `numpy`, `PIL`, `opencv-python`, `scipy`

---

### 阶段2: 模型管理模块（预计 2-3 小时）

#### Task 2.1: 模型管理器
**文件**: `src/ptcgp_auto_v2/infra/model_manager.py` (新建)
**功能**:
1. 从 `ptcgp-assets` 下载模型
2. 异步加载YOLO模型
3. 管理模型状态
4. **区分平台下载**：macOS使用CoreML格式（.mlpackage目录），其他平台使用PyTorch格式（.pt文件）

**模型配置**:
```python
# 模型子目录和名称（来自 yolo-card-training 的训练结果）
MODEL_SUBDIR = "yolo11n-5k-25-2026.02.02"
MODEL_NAME = "best"  # 对应 best.pt 或 best.mlpackage
```

**核心代码**:
```python
import json
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
MODELS_BASE_URL = f"https://cdn.jsdelivr.net/gh/{ASSETS_REPO}@main/models"
GITHUB_API_URL = f"https://api.github.com/repos/{ASSETS_REPO}/contents"

# 模型配置
MODEL_SUBDIR = "yolo11n-5k-25-2026.02.02"
MODEL_NAME = "best"


class ModelManager:
    """YOLO模型管理器"""

    def __init__(self, models_dir: str = "data/models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._model: Optional["YOLO"] = None
        self._model_ready = threading.Event()
        self._lock = threading.Lock()
        self._session = requests.Session()

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
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"下载文件失败 {url}: {e}")
            return False

    def _download_directory(self, api_path: str, local_dir: Path) -> bool:
        """
        递归下载 GitHub 仓库中的目录
        
        用于下载 CoreML 模型包（.mlpackage 是一个目录）
        """
        try:
            url = f"{GITHUB_API_URL}/{api_path}?ref=main"
            response = self._session.get(url, timeout=30)
            response.raise_for_status()
            items = response.json()

            success = True
            for item in items:
                item_name = item["name"]
                item_type = item["type"]
                item_path = item["path"]
                local_item_path = local_dir / item_name

                if item_type == "file":
                    download_url = item["download_url"]
                    if not self._download_file(download_url, local_item_path):
                        success = False
                elif item_type == "dir":
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
            logger.info(f"模型已存在: {model_path}")
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
                global YOLO
                if YOLO is None:
                    from ultralytics import YOLO as _YOLO
                    YOLO = _YOLO

                model_path = self.get_model_path()

                # 1. 确保模型已下载
                if not model_path.exists():
                    logger.info("模型不存在，开始下载...")
                    if not self.download_model():
                        logger.error("模型下载失败，无法加载")
                        return

                # 2. 加载模型
                logger.info(f"正在加载YOLO模型: {model_path}")
                with self._lock:
                    self._model = YOLO(str(model_path))
                    self._model_ready.set()

                logger.info("YOLO模型加载完成，识别功能已就绪")

            except Exception as e:
                logger.error(f"加载模型失败: {e}", exc_info=True)

        # 启动后台线程加载模型
        thread = threading.Thread(target=_load, daemon=True, name="ModelLoader")
        thread.start()
        logger.info("模型加载线程已启动")

    def is_model_ready(self) -> bool:
        """检查模型是否加载完成"""
        return self._model_ready.is_set()

    def wait_for_model(self, timeout: Optional[float] = None) -> bool:
        """等待模型加载完成"""
        return self._model_ready.wait(timeout=timeout)

    def get_model(self) -> Optional["YOLO"]:
        """获取已加载的模型"""
        with self._lock:
            return self._model


# 全局单例
_model_manager_instance: Optional[ModelManager] = None
_model_manager_lock = threading.Lock()


def get_model_manager() -> ModelManager:
    """获取全局模型管理器单例"""
    global _model_manager_instance
    if _model_manager_instance is None:
        with _model_manager_lock:
            if _model_manager_instance is None:
                _model_manager_instance = ModelManager()
    return _model_manager_instance
```

**说明**:
- **模型来源**: `shelken/ptcgp-assets/models/yolo11n-5k-25-2026.02.02/`
- **macOS**: 下载 `best.mlpackage` 目录（CoreML格式，通过GitHub API递归下载）
- **其他平台**: 下载 `best.pt` 文件（PyTorch格式）
- **本地路径**: `data/models/yolo11n-5k-25-2026.02.02/best.{mlpackage|pt}`

---

#### Task 2.2: 改造 ImageResourceManager 下载逻辑
**文件**: `src/ptcgp_auto_v2/utils/image_manager.py`
**修改内容**:
1. **替换下载源**: 从 `flibustier/pokemon-tcg-exchange` 改为 `shelken/ptcgp-assets`
2. **简化下载逻辑**: 不再裁剪和重命名，直接下载原始 PNG 图片
3. **调整存储路径**: 使用 `templates/cards/{set_code}/{number:03d}.png`（与 `ptcgp-assets` 目录结构一致）
4. **保留原有接口**: `ensure_series_ready`, `ensure_pack_ready`, `ensure_card_ready` 方法签名不变

**关键修改**:
```python
# 修改前
IMAGE_BASE_URL = "https://raw.githubusercontent.com/flibustier/pokemon-tcg-exchange/main/public/images"
# 修改后  
IMAGE_BASE_URL = "https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/images/zh-TW/cards-by-set"

# 修改前：下载后裁剪处理
# 修改后：直接保存原始图片
def _download_and_save(self, card: Card) -> bool:
    url = f"{IMAGE_BASE_URL}/{card.set_code}/{card.number:03d}.png"
    save_dir = self.cards_dir / card.set_code
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{card.number:03d}.png"
    
    if save_path.exists():
        return True
    
    try:
        resp = self.session.get(url, timeout=30)
        if resp.status_code == 200:
            save_path.write_bytes(resp.content)
            # 更新数据库记录
            with Session(get_engine()) as session:
                db_card = session.get(Card, card.id)
                if db_card:
                    db_card.local_image_path = str(save_path)
                    session.add(db_card)
                    session.commit()
            return True
    except Exception as e:
        logger.warning(f"下载失败 {url}: {e}")
    return False
```

**说明**:
- 删除裁剪、缩放相关代码（`_crop_and_resize`, `TARGET_WIDTH`, `CROP_BOX_RATIO`）
- 删除 `pack_name` 子目录层级，直接按系列存储
- 保留并发下载能力（`_process_cards_parallel`）
- 保留 `ImageResourceManager` 类名和主要接口，避免其他调用方改动

---

### 阶段3: Hash管理模块（预计 3-4 小时）

#### Task 3.1: 改造 ImageResourceManager 复用
**文件**: `src/ptcgp_auto_v2/utils/image_manager.py`（复用 Task 2.2 改造后的版本）
**说明**: 不需要新建 `card_image_downloader.py`，直接使用改造后的 `ImageResourceManager`:
```python
from ptcgp_auto_v2.utils.image_manager import ImageResourceManager

class CardHashManager:
    def __init__(self):
        self._downloader = ImageResourceManager()  # 复用改造后的下载器
```

**核心代码**:
```python
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from io import BytesIO

# 使用 jsDelivr CDN 加速下载，避免 GitHub 速率限制
ASSETS_BASE_URL = "https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/images/zh-TW/cards-by-set"

class CardImageDownloader:
    """卡牌图片下载器"""
    
    def __init__(self, cards_dir: str = "templates/cards"):
        self.cards_dir = Path(cards_dir)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
    
    def download_card(self, set_code: str, card_number: int) -> Optional[Path]:
        """下载单张卡牌图片"""
        url = f"{ASSETS_BASE_URL}/{set_code}/{card_number:03d}.png"
        
        save_dir = self.cards_dir / set_code
        save_dir.mkdir(parents=True, exist_ok=True)
        
        save_path = save_dir / f"{card_number:03d}.png"
        if save_path.exists():
            return save_path
        
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                save_path.write_bytes(response.content)
                return save_path
        except Exception as e:
            logger.warning(f"下载卡牌 {set_code}/{card_number} 失败: {e}")
        
        return None
    
    def download_cards_batch(self, set_code: str, card_numbers: List[int], max_workers: int = 5) -> Dict[int, Path]:
        """批量下载卡牌图片"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_card = {
                executor.submit(self.download_card, set_code, num): num 
                for num in card_numbers
            }
            
            for future in as_completed(future_to_card):
                card_num = future_to_card[future]
                try:
                    path = future.result()
                    if path:
                        results[card_num] = path
                except Exception as e:
                    logger.error(f"下载卡牌 {card_num} 出错: {e}")
        
        return results
```

---

#### Task 3.2: Hash索引管理器
**文件**: `src/ptcgp_auto_v2/infra/card_hash_manager.py` (新建)
**功能**:
1. 管理内存中的Hash索引
2. 确保系列Hash就绪（下载缺失卡牌并计算Hash）
3. 提供匹配接口

**核心代码**:
```python
import base64
import logging
from typing import Dict, List, Optional, Set
import numpy as np
from pathlib import Path
from PIL import Image

from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.utils.perceptual_hash import (
    pil_to_color_pixels,
    calculate_perceptual_hash,
    encode_hash_to_base64,
    decode_hash_from_base64,
    calculate_similarity
)
from ptcgp_auto_v2.utils.image_manager import ImageResourceManager

logger = logging.getLogger(__name__)

class CardHashManager:
    """卡牌Hash管理器"""
    
    def __init__(self):
        # 按系列索引（开包识别用）
        self._series_cache: Dict[str, Dict[int, np.ndarray]] = {}
        # 全局索引（跨系列检测用）
        self._global_cache: Dict[str, np.ndarray] = {}  # key: "A1/001"
        self._loaded_sets: Set[str] = set()
        self._all_loaded: bool = False
        # 内存缓存：记录下载失败的卡牌，避免重复尝试（按卡牌粒度）
        self._failed_downloads: Set[str] = set()  # 格式: "{set_code}/{number:03d}"
        self._repo = CardRepository()
        self._downloader = ImageResourceManager()  # 复用改造后的下载器
    
    def ensure_series_ready(self, set_code: str) -> bool:
        """确保某系列所有卡牌都有Hash值（下载缺失卡牌并计算）"""
        # 1. 查询缺失Hash的卡牌
        all_missing = self._repo.get_cards_without_hash(set_code)
        
        # 2. 过滤掉已下载失败的卡牌（内存缓存，避免重复尝试）
        missing_cards = [
            card for card in all_missing
            if f"{set_code}/{card.number:03d}" not in self._failed_downloads
        ]
        
        skipped_count = len(all_missing) - len(missing_cards)
        if skipped_count > 0:
            logger.debug(f"系列 {set_code} 跳过 {skipped_count} 张已知下载失败的卡牌")
        
        if missing_cards:
            logger.info(f"系列 {set_code} 有 {len(missing_cards)} 张卡牌缺少Hash，开始处理...")
            
            # 3. 下载缺失卡牌的图片
            card_numbers = [card.number for card in missing_cards]
            downloaded = self._downloader.download_cards_batch(set_code, card_numbers)
            
            # 4. 计算Hash并更新数据库
            success_count = 0
            for card in missing_cards:
                if card.number in downloaded:
                    if self._compute_and_save_hash(card.id, downloaded[card.number]):
                        success_count += 1
                else:
                    # 下载失败，记录到内存缓存，本次运行不再尝试
                    self._failed_downloads.add(f"{set_code}/{card.number:03d}")
                    logger.warning(f"卡牌 {set_code}/{card.number:03d} 下载失败，已标记为失败（本次运行不再尝试）")
            
            logger.info(f"系列 {set_code} Hash计算完成: {success_count}/{len(missing_cards)} 张成功")
        
        # 5. 加载系列Hash到内存
        self._load_series_hash(set_code)
        
        return True
    
    def _compute_and_save_hash(self, card_id: int, image_path: Path) -> bool:
        """计算图片Hash并保存到数据库"""
        try:
            # 读取图片
            pil_img = Image.open(image_path)
            
            # 计算Hash
            color_pixels = pil_to_color_pixels(pil_img)
            hash_arr = calculate_perceptual_hash(color_pixels)
            
            # 编码为Base64
            hash_str = encode_hash_to_base64(hash_arr)
            
            # 更新数据库
            return self._repo.update_card_hash(card_id, hash_str)
        except Exception as e:
            logger.error(f"计算卡牌 {card_id} Hash失败: {e}")
            return False
    
    def _load_series_hash(self, set_code: str):
        """加载某系列Hash到内存（系列模式）"""
        if set_code in self._loaded_sets:
            return
        
        hash_data = self._repo.get_cards_with_hash_by_set(set_code)
        
        self._series_cache[set_code] = {
            number: decode_hash_from_base64(hash_str) 
            for number, hash_str in hash_data.items()
        }
        self._loaded_sets.add(set_code)
        
        logger.info(f"系列 {set_code} Hash索引加载完成，共 {len(hash_data)} 张卡牌")
    
    def load_all_hashes(self) -> bool:
        """加载所有系列Hash到内存（全局模式）"""
        if self._all_loaded:
            return True
        
        # 获取所有系列
        all_sets = self._repo.get_all_sets()
        
        for card_set in all_sets:
            set_code = card_set.code
            # 确保系列就绪（下载缺失图片并计算Hash）
            self.ensure_series_ready(set_code)
            # 加载到全局缓存
            if set_code in self._series_cache:
                for number, hash_arr in self._series_cache[set_code].items():
                    self._global_cache[f"{set_code}/{number:03d}"] = hash_arr
        
        self._all_loaded = True
        logger.info(f"全局Hash索引加载完成，共 {len(self._global_cache)} 张卡牌")
        return True
    
    def find_best_match(
        self, 
        target_hash: np.ndarray,
        set_code: Optional[str] = None,
        threshold: float = 0.8
    ) -> Optional[Tuple]:
        """
        查找最佳匹配的卡牌
        
        Args:
            target_hash: 目标Hash值
            set_code: 指定系列代码，为None则全局搜索
            threshold: 相似度阈值
        
        Returns:
            - 系列模式 (set_code指定): (card_number, similarity)
            - 全局模式 (set_code=None): (set_code, card_number, similarity)
            - 无匹配: None
        """
        if set_code is None:
            return self._find_best_match_globally(target_hash, threshold)
        else:
            return self._find_best_match_in_series(set_code, target_hash, threshold)
    
    def _find_best_match_in_series(
        self, 
        set_code: str, 
        target_hash: np.ndarray, 
        threshold: float
    ) -> Optional[Tuple[int, float]]:
        """在指定系列中查找最佳匹配"""
        if set_code not in self._series_cache:
            self._load_series_hash(set_code)
        
        series_hashes = self._series_cache.get(set_code, {})
        if not series_hashes:
            return None
        
        best_match = None
        best_similarity = 0.0
        
        for card_number, card_hash in series_hashes.items():
            similarity = calculate_similarity(target_hash, card_hash)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = card_number
        
        if best_match and best_similarity >= threshold:
            return (best_match, best_similarity)
        
        return None
    
    def _find_best_match_globally(
        self,
        target_hash: np.ndarray,
        threshold: float
    ) -> Optional[Tuple[str, int, float]]:
        """在所有已加载系列中查找最佳匹配（跨系列检测）"""
        # 确保全局索引已加载
        if not self._all_loaded:
            self.load_all_hashes()
        
        if not self._global_cache:
            return None
        
        best_match = None
        best_similarity = 0.0
        
        for key, card_hash in self._global_cache.items():
            similarity = calculate_similarity(target_hash, card_hash)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = key
        
        if best_match and best_similarity >= threshold:
            # 解析 key: "A1/001"
            set_code, card_number_str = best_match.split('/')
            card_number = int(card_number_str)
            return (set_code, card_number, best_similarity)
        
        return None
    
    def get_loaded_sets(self) -> Set[str]:
        """获取已加载的系列列表"""
        return self._loaded_sets.copy()
    
    def is_all_loaded(self) -> bool:
        """检查是否已加载所有系列"""
        return self._all_loaded
    
    def clear_failed_cache(self, set_code: Optional[str] = None) -> int:
        """
        强制刷新：清空下载失败缓存
        
        使用场景：当远程仓库补充了缺失的卡牌后，调用此方法重新尝试下载
        
        Args:
            set_code: 指定系列代码则只清空该系列的失败缓存，为None则清空全部
        
        Returns:
            清空的缓存条目数量
        """
        if set_code is None:
            count = len(self._failed_downloads)
            self._failed_downloads.clear()
            logger.info(f"已清空所有失败缓存（共 {count} 条）")
            return count
        else:
            # 只清空指定系列的失败缓存
            to_remove = {k for k in self._failed_downloads if k.startswith(f"{set_code}/")}
            for key in to_remove:
                self._failed_downloads.discard(key)
            logger.info(f"已清空系列 {set_code} 的失败缓存（共 {len(to_remove)} 条）")
            return len(to_remove)
    
    def get_failed_count(self, set_code: Optional[str] = None) -> int:
        """
        获取下载失败的卡牌数量
        
        Args:
            set_code: 指定系列代码则只统计该系列，为None则统计全部
        
        Returns:
            失败缓存条目数量
        """
        if set_code is None:
            return len(self._failed_downloads)
        else:
            return sum(1 for k in self._failed_downloads if k.startswith(f"{set_code}/"))
```

---

### 阶段4: YOLO卡牌识别器（预计 4-5 小时）

#### Task 4.1: YOLO卡牌识别器
**文件**: `src/ptcgp_auto_v2/infra/yolo_card_recognizer.py` (新建)
**功能**: 
1. YOLO检测卡牌位置
2. 透视变换裁剪卡牌
3. 计算Hash并匹配
4. 返回识别结果

**核心代码**:
```python
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np
import cv2
from PIL import Image

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.model_manager import ModelManager
from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager
from ptcgp_auto_v2.utils.perceptual_hash import bgr_to_color_pixels, calculate_perceptual_hash

logger = logging.getLogger(__name__)

@dataclass
class DetectedCard:
    """检测到的卡牌"""
    card_number: int  # 卡牌编号
    confidence: float  # YOLO检测置信度
    similarity: float  # Hash匹配相似度
    bbox: Tuple[int, int, int, int]  # 边框坐标 (x1, y1, x2, y2)
    center: Tuple[float, float]  # 中心点坐标 (用于排序)


class YoloCardRecognizer:
    """YOLO+Hash卡牌识别器"""
    
    # 默认阈值（从 constants.py 统一引用）
    DEFAULT_OBB_THRESHOLD = YOLO_OBB_THRESHOLD  # YOLO检测置信度阈值
    DEFAULT_SIMILARITY_THRESHOLD = HASH_SIMILARITY_THRESHOLD  # Hash匹配相似度阈值
    
    # 基准分辨率像素常量（基于1080x1920标准分辨率）
    # 这些值来源于 yolo-card-training/scripts/test_massive_matching.py 测试验证
    BASE_TARGET_WIDTH = YOLO_BASE_TARGET_WIDTH  # 透视变换后卡牌宽度基准值
    BASE_TARGET_HEIGHT = YOLO_BASE_TARGET_HEIGHT  # 透视变换后卡牌高度基准值
    BASE_ROW_THRESHOLD = YOLO_BASE_ROW_THRESHOLD  # 同一行卡牌Y坐标差异阈值基准值
    
    def __init__(
        self, 
        adb: AdbController, 
        model_manager: ModelManager,
        hash_manager: CardHashManager
    ):
        self.adb = adb
        self.model_manager = model_manager
        self.hash_manager = hash_manager
    
    def scan_pack_result(
        self, 
        set_code: str,
        obb_threshold: float = DEFAULT_OBB_THRESHOLD,
     similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
 ) -> List[DetectedCard]:
        """扫描开包结果页，返回识别到的卡牌列表"""
        # 1. 确保模型已加载
        if not self.model_manager.is_model_ready():
            logger.warning("YOLO模型尚未加载完成")
            return []
        
        # 2. 确保系列Hash已就绪
        if not self.hash_manager.ensure_series_ready(set_code):
            logger.error(f"无法确保系列 {set_code} Hash就绪")
            return []
        
        # 3. 截图
        screenshot = self.adb.screenshot()
        if not screenshot:
            logger.error("截图失败")
            return []
        
        # 4. YOLO检测卡牌
        detected_cards = self._detect_cards(screenshot, obb_threshold)
        if not detected_cards:
            logger.info("未检测到卡牌")
            return []
        
        # 5. 对每张检测到的卡牌进行Hash匹配
        results = []
        for card_info in detected_cards:
            # 裁剪卡牌图片
            cropped = card_info['cropped']
            
            # 计算Hash
            color_pixels = bgr_to_color_pixels(cropped)
            card_hash = calculate_perceptual_hash(color_pixels)
            
            # 匹配最佳卡牌（系列模式）
            match = self.hash_manager.find_best_match(
                card_hash, set_code=set_code, threshold=similarity_threshold
            )
            
            if match:
                card_number, similarity = match
                 results.append(DetectedCard(
                    card_number=card_number,
                    confidence=card_info['confidence'],
                    similarity=similarity,
                    bbox=card_info['bbox'],
                    center=card_info['center']
                ))
        
        # 6. 按阅读顺序排序（先行后列：从上到下，从左到右）
         results = self._sort_by_reading_order(results)
        
        logger.info(f"识别完成: {len(results)}/{len(detected_cards)} 张卡牌匹配成功")
        return results
    
    def _detect_cards(
        self, 
        screenshot: Image.Image, 
        conf_threshold: float
    ) -> List[dict]:
        """使用YOLO检测卡牌位置"""
        model = self.model_manager.get_model()
        
        # PIL -> numpy (BGR)
        img_array = np.array(screenshot)
        if len(img_array.shape) == 3 and img_array.shape[2] == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # YOLO推理
        results = model(img_bgr, verbose=False)
        result = results[0]
        
        if result.obb is None or len(result.obb) == 0:
            return []
        
        detected = []
        for i, obb in enumerate(result.obb):
            conf = float(obb.conf[0].item())
            
            if conf < conf_threshold:
                continue
            
            # 使用矩形框裁剪
            if hasattr(obb, 'xyxy') and obb.xyxy is not None:
                x1, y1, x2, y2 = map(int, obb.xyxy[0])
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(img_bgr.shape[1], x2), min(img_bgr.shape[0], y2)
                cropped = img_bgr[y1:y2, x1:x2]
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
            else:
                # 备用：使用旋转框透视变换
                xyxyxyxy = obb.xyxyxyxy[0].cpu().numpy().reshape(-1, 2)
                corners = xyxyxyxy.astype(np.float32)
                # 根据当前分辨率缩放基准尺寸
                target_w = self.adb.scaled_x(self.BASE_TARGET_WIDTH)
                target_h = self.adb.scaled_y(self.BASE_TARGET_HEIGHT)
                dst = np.array([[0, 0], [target_w, 0], [target_w, target_h], [0, target_h]], dtype=np.float32)
                matrix = cv2.getPerspectiveTransform(corners, dst)
                cropped = cv2.warpPerspective(img_bgr, matrix, (target_w, target_h))
                center_x = corners[:, 0].mean()
                center_y = corners[:, 1].mean()
                x1, y1 = int(corners[:, 0].min()), int(corners[:, 1].min())
                x2, y2 = int(corners[:, 0].max()), int(corners[:, 1].max())
            
            detected.append({
                'index': i + 1,
                'confidence': conf,
                'cropped': cropped,
                'bbox': (x1, y1, x2, y2),
                'center': (center_x, center_y)
            })
        
        return detected
    
     def _sort_by_reading_order(self, cards: List[DetectedCard]) -> List[DetectedCard]:
        """按阅读顺序排序：从上到下，从左到右"""
        if not cards:
            return cards
        
        # 按Y坐标分组（同一行的卡牌Y坐标相近）
        sorted_by_y = sorted(cards, key=lambda c: c.center[1])
        
        rows = []
        current_row = [sorted_by_y[0]]
         # 根据当前分辨率缩放行阈值（基准10px对应1080x1920）
         row_threshold = self.adb.scaled_y(self.BASE_ROW_THRESHOLD)  # Y坐标相差小于阈值视为同一行
        
        for card in sorted_by_y[1:]:
            if abs(card.center[1] - current_row[0].center[1]) < row_threshold:
                current_row.append(card)
            else:
                # 当前行结束，按X坐标排序并保存
                current_row.sort(key=lambda c: c.center[0])
                rows.append(current_row)
                current_row = [card]
        
        # 处理最后一行
        if current_row:
            current_row.sort(key=lambda c: c.center[0])
            rows.append(current_row)
        
        # 合并所有行
        result = []
        for row in rows:
            result.extend(row)
        
         return result

**实现备注**:
- 当前实现会将每次识别的裁剪卡牌输出到 `output/recognition_debug/<label>_<timestamp>/` 目录，便于离线排查。
```

---

### 阶段5: 整合与修改（预计 2-3 小时）

#### Task 5.1: 修改 constants.py
**文件**: `src/ptcgp_auto_v2/config/constants.py`
**新增常量**:
```python
# YOLO+Hash 识别配置
YOLO_OBB_THRESHOLD = 0.95  # YOLO检测置信度阈值（来自 test_massive_matching.py 实测验证）
HASH_SIMILARITY_THRESHOLD = 0.7  # Hash匹配相似度阈值
```

**说明**:
- `HASH_SIZE` / `FREQ_SIZE` 仍在 `src/ptcgp_auto_v2/utils/perceptual_hash.py` 内部维护（当前实现未上移到 constants）。
- YOLO 识别器基准像素值仍定义在 `src/ptcgp_auto_v2/infra/yolo_card_recognizer.py` 内部常量。

**模型管理器常量（位于 `src/ptcgp_auto_v2/infra/model_manager.py`）**:
```python
ASSETS_REPO = "shelken/ptcgp-assets"
MODELS_BASE_URL = f"https://cdn.jsdelivr.net/gh/{ASSETS_REPO}@main/models"
GITHUB_API_URL = f"https://api.github.com/repos/{ASSETS_REPO}/contents"

MODEL_SUBDIR = "yolo11n-5k-25-2026.02.02"
MODEL_NAME = "best"  # best.pt 或 best.mlpackage

# ModelManager 默认参数
# models_dir = "data/models"
```

---

#### Task 5.2: 修改 main_v2.py 启动流程
**文件**: `src/ptcgp_auto_v2/main.py`
**修改**: 在应用启动时异步加载YOLO模型（使用全局单例）

**代码模板**:
```python
# 在 main() 函数开头
from ptcgp_auto_v2.infra.model_manager import get_model_manager

# 启动时异步加载YOLO模型
model_manager = get_model_manager()
model_manager.load_model_async()
logger.info("YOLO模型异步加载已启动...")
```

**说明**:
- 使用全局单例 `get_model_manager()`，无需传递实例
- 模型加载在后台线程进行，不阻塞主流程
- `OpenPackTask` 直接使用 `get_model_manager()` 获取实例

---

#### Task 5.3: 修改 OpenPackTask
**文件**: `src/ptcgp_auto_v2/tasks/open_pack.py`
**修改**: 
1. 使用 `YoloCardRecognizer` 替换 `CardRecognizer`
2. 修改 `_recognize_cards()` 方法
3. 在 `on_start()` 中预加载目标系列Hash

**修改点1: 初始化方法**:
```python
def __init__(self, adb, recognizer, page_detector):
    super().__init__(adb, recognizer, page_detector)
    
    # 新的识别器
    from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer
    from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager
    from ptcgp_auto_v2.infra.model_manager import get_model_manager
    
    self.hash_manager = CardHashManager()
    model_manager = get_model_manager()  # 使用全局单例
    self.card_recognizer = YoloCardRecognizer(
        adb, model_manager, self.hash_manager
    )
```

**修改点2: on_start 预加载Hash**:
```python
def on_start(self):
    # ... 原有代码 ...
    
    # 预加载目标系列Hash（在后台准备）
    if self.target_pack and self.hash_manager:
        pack_code = self.target_pack.get("pack_code")
        if pack_code:
            # 异步预加载（不阻塞流程，实际扫描时会等待完成）
            threading.Thread(
                target=self.hash_manager.ensure_series_ready,
                args=(pack_code,),
                daemon=True
            ).start()
```

**修改点3: 修改 _recognize_cards**:
```python
def _recognize_cards(self):
    """使用YOLO+Hash识别卡牌"""
    if not self.card_recognizer:
        logger.error("卡牌识别器未初始化")
        return
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            set_code = self.target_pack.get("pack_code") if self.target_pack else None
            if not set_code:
                logger.error("未配置目标系列")
                return
            
            # 扫描识别（当前实现使用更严格的相似度阈值 0.68）
            detected_cards = self.card_recognizer.scan_pack_result(
                set_code, similarity_threshold=0.68
            )
            
            if detected_cards:
                # 转换检测结果为原有格式并保存
                self._save_recognized_cards(detected_cards, set_code)
                self._result_recognized = True
                break
            else:
                if attempt < max_retries - 1:
                    logger.debug(f"未识别到卡牌，等待重试 ({attempt + 1}/{max_retries})")
                    time.sleep(2.0)
                else:
                    logger.warning(f"卡牌识别连续失败 {max_retries} 次")
                    self._result_recognized = True
                    
        except Exception as e:
            logger.error(f"识别卡牌失败: {e}")
            if attempt >= max_retries - 1:
                self._result_recognized = True

def _save_recognized_cards(self, detected_cards: List[DetectedCard], set_code: str):
    """保存识别结果到数据库"""
    # 转换 DetectedCard 为原有格式
    current_batch_cards = []
    
    for i, card in enumerate(detected_cards):
        # 通过编号查询卡牌详情
        card_obj = self._card_repo.get_card_by_set_and_number(set_code, card.card_number)
        
        card_data = {
            "card_name": card_obj.name if card_obj else f"Card #{card.card_number}",
            "rarity": card_obj.rarity if card_obj else "Unknown",
            "card_id": card_obj.id if card_obj else None,
            "is_new": False,
            "position": i + 1,
            "confidence": float(card.confidence),  # 使用YOLO置信度作为置信度
        }
        current_batch_cards.append(card_data)
    
    # 保存到数据库（原有逻辑）
    if self._pack_record_repo and self.account.id:
        try:
            pack_type = "daily_free"
            pack_code = self.target_pack.get("pack_code") if self.target_pack else None
            pack_name = self.target_pack.get("booster_name") if self.target_pack else None
            
            self._pack_record_repo.create_for_account(
                self.account.id,
                pack_type=pack_type,
                pack_code=pack_code,
                pack_name=pack_name,
                cards=current_batch_cards,
            )
            logger.info(f"已保存开包记录: {pack_code}/{pack_name} ({len(current_batch_cards)} 张)")
        except Exception as e:
            logger.error(f"保存开包记录失败: {e}")
```

---

#### Task 5.4: 更新项目文档
**文件**: 
- `README.md`
- `AGENTS.md`

**更新内容**:
1. **README.md**: 
   - 添加 YOLO+Hash 识别功能的说明
   - 更新架构图，包含新的 infra 模块
   - 添加模型自动下载的说明
   - 更新依赖列表（ultralytics, opencv-python 等）

2. **AGENTS.md**:
   - 更新核心架构部分，添加 YoloCardRecognizer、CardHashManager、ModelManager
   - 更新文件结构概览
   - 添加感知哈希配置说明
   - 更新调试与开发章节，说明新增任务的方式

**说明**:
- 保持中英文对照（标题英文，内容中文）
- 由于仓库当前未包含 `CLAUDE.md`，实际以 `AGENTS.md` 为准更新

---

### 阶段6: 测试与验证（预计 2-3 小时）

#### Task 6.1: 编写单元测试
**文件**: `src/ptcgp_auto_v2/tests/infra/test_yolo_recognition.py` (新建)
**测试内容**:
1. 测试感知哈希计算和匹配
2. 测试Hash Manager的加载和匹配功能
3. 测试识别结果排序逻辑

---

#### Task 6.2: 集成测试
**测试场景**:
1. 模型未加载完成场景测试
2. Hash 未就绪场景测试
3. 排序逻辑与全局扫描路径测试

**文件**: `src/ptcgp_auto_v2/tests/test_integration.py` (新建)

---

#### Task 6.3: 性能基准测试
**文件**: `scripts/benchmark_recognition.py` (新建)
**测试指标**:
- YOLO检测耗时
- Hash计算耗时
- Hash匹配耗时（单张 vs 批量）
- 全流程耗时

**运行前置**:
- CoreML 推理依赖 `coremltools`，推荐使用 uv 安装
  ```bash
  uv pip install "coremltools>=9.0" "numpy>=1.14.5,<=2.3.5"
  ```

---

## 文件结构变更

```
src/ptcgp_auto_v2/
├── config/constants.py                    # 新增YOLO相关常量
├── db/
│   ├── models/card.py                     # 新增perceptual_hash字段
│   └── repositories/card_repository.py    # 新增Hash相关查询方法
├── infra/
│   ├── model_manager.py                   # [新建] 模型下载和管理
│   ├── card_hash_manager.py               # [新建] Hash索引管理
│   └── yolo_card_recognizer.py            # [新建] YOLO识别器
├── utils/
│   ├── perceptual_hash.py                 # [新建] 哈希计算工具
│   └── image_manager.py                   # [改造] 替换下载源为ptcgp-assets
└── tasks/open_pack.py                     # [修改] 使用YOLO+Hash替换模板匹配

scripts/
├── migration_add_hash_field.py            # [新建] 数据库迁移
└── benchmark_recognition.py               # [新建] 性能测试

data/
└── models/                                # [新建目录] 存放下载的YOLO模型
    └── card_obb5.mlpackage                # macOS CoreML模型
```

---

## 时间估算

| 阶段 | 任务数 | 预估时间 |
|------|--------|----------|
| 阶段1: 基础设施 | 4 | 2-3 小时 |
| 阶段2: 模型管理 | 2 | 2-3 小时 |
| 阶段3: Hash管理 | 2 | 3-4 小时 |
| 阶段4: 识别器 | 1 | 4-5 小时 |
| 阶段5: 整合 | 4 | 2-3 小时 |
| 阶段6: 测试 | 3 | 2-3 小时 |
| **总计** | **16** | **15-21 小时** |

---

## 执行建议

1. **按阶段执行**: 每个阶段完成后再进入下一阶段，便于测试和问题定位
2. **先跑通流程**: 阶段4完成后，先进行一次完整测试确保流程可行
3. **强制替换**: 本次实施**完全替换**模板匹配，不保留 fallback（已在计划中移除所有 fallback 逻辑）
4. **模型加载检查**: 如果模型加载失败，YOLO 识别器会直接报错/返回空结果，不会自动回退到旧方法
5. **阶段5任务计数更新**: 新增 Task 5.4 文档更新任务，确保 README 和 CLAUDE.md 同步更新


---

## 下一步

**请选择执行方式**:
1. **子agent并行执行**: 每个阶段分配一个子agent，您在此会话监督
2. **逐个Task执行**: 您亲自执行，完成后我review并提供下一个Task
3. **一次性实现**: 我直接编写所有文件（适合您信任我的判断）

**或者提出修改意见**: 对这个计划有任何疑问或需要调整的地方？

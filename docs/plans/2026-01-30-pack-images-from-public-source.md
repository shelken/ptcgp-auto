# 卡包封面改用公共资源实施计划

## 背景

目前开包任务使用手动裁剪的卡包封面模板（位于 `templates/packs/{pack_code}/{booster}.png`），每次新卡包发布都需要手动执行 `python debug_tool.py -a PORT --crop-pack` 来裁剪游戏截图。现在需要改用公共资源自动下载和处理。

## 目标

1. 自动从 `https://github.com/flibustier/pokemon-tcg-exchange/tree/main/public/images/packs` 下载卡包封面
2. 动态裁剪和缩放到适合模板匹配的尺寸
3. 保存到 `templates/packs_auto/{booster}.png`
4. 支持测试流程验证匹配效果

## 技术细节

### 公共图片资源
- **基础 URL**: `https://raw.githubusercontent.com/flibustier/pokemon-tcg-exchange/main/public/images/packs/`
- **格式**: WebP (160x256 像素)
- **命名**: 直接使用子包名称（如 `Charizard.webp`, `Mewtwo.webp`）

### 当前手动模板规格
- **格式**: PNG
- **尺寸**: 约 513x566 像素（因设备和裁剪区域而异）
- **路径**: `templates/packs/{pack_code}/{booster}.png`

### 需要确定的参数
1. **目标尺寸**: 需要测试确定最佳尺寸（预计 400-600px 宽度）
2. **裁剪区域**: 公共图片 160x256 需要裁剪掉边框部分
3. **缩放比例**: 根据目标设备分辨率确定

## 实施步骤

### 阶段 1: 基础设施 (Day 1)

#### 1.1 创建 PackImageManager 类
**文件**: `src/ptcgp_auto_v2/utils/pack_image_manager.py`

**功能**:
- 下载卡包图片（从 GitHub raw URL）
- 裁剪和缩放处理
- 保存到指定目录
- 检查资源是否存在

**关键参数**（待测试调整）:
```python
# 裁剪比例 (left, top, right, bottom) - 去除边框
PACK_CROP_RATIO = (0.05, 0.05, 0.95, 0.95)

# 目标宽度（基于 1080p 基准）
TARGET_WIDTH = 450  # 待测试调整

# 图片基础 URL
PACK_IMAGE_BASE_URL = "https://raw.githubusercontent.com/flibustier/pokemon-tcg-exchange/main/public/images/packs"
```

**类设计**:
```python
class PackImageManager:
    def __init__(self, base_dir: str = "templates/packs_auto"):
        pass
    
    def ensure_pack_ready(self, booster_name: str) -> bool:
        """确保指定卡包图片已准备就绪"""
        pass
    
    def is_pack_ready(self, booster_name: str) -> bool:
        """检查卡包图片是否已存在且有效"""
        pass
    
    def download_pack_image(self, booster_name: str) -> Optional[bytes]:
        """下载卡包图片"""
        pass
    
    def process_and_save(self, booster_name: str, image_data: bytes) -> bool:
        """处理并保存卡包图片"""
        pass
    
    def get_pack_path(self, booster_name: str) -> Path:
        """获取卡包图片保存路径"""
        pass
```

#### 1.2 修改 template.py
**文件**: `src/ptcgp_auto_v2/infra/template.py`

**修改内容**:
- 修改 `load_core_templates` 方法，仅加载一级目录 (`templates/*.png`) 下的模板
- 排除 `cards/`、`packs/`、`packs_auto/` 等子目录

**代码变更**:
```python
def load_core_templates(self, screen_width: Optional[int] = None):
    # ... 现有代码 ...
    for file in self.templates_dir.glob("*.png"):  # 只加载一级目录
        # 不再使用 **/*.png 递归加载
        if self._load_template_file(file):
            count += 1
    # ... 后续代码 ...
```

#### 1.3 更新 .gitignore
**文件**: `.gitignore`

**添加**:
```
templates/packs_auto/
```

### 阶段 2: 业务逻辑集成 (Day 2)

#### 2.1 修改 open_pack.py
**文件**: `src/ptcgp_auto_v2/tasks/open_pack.py`

**修改内容**:

1. **更新 `_prepare_image_resources` 方法**:
```python
def _prepare_image_resources(self):
    """准备图片资源（按需加载）"""
    pack_code = self.target_pack.get("pack_code") if self.target_pack else None
    booster_name = self.target_pack.get("booster_name") if self.target_pack else None
    if not pack_code or not booster_name:
        return

    try:
        from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager
        
        manager = PackImageManager()
        # 确保目标卡包图片已就绪
        if manager.ensure_pack_ready(booster_name):
            # 动态加载模板
            if self.recognizer:
                _, template_matcher = self.recognizer
                # 加载单个卡包模板（新接口）
                template_matcher.load_single_template(
                    manager.get_pack_path(booster_name)
                )
    except Exception as e:
        logger.error(f"准备卡包图片资源失败: {e}")
```

2. **更新 `_get_target_template_name` 方法**:
```python
def _get_target_template_name(self) -> Optional[str]:
    """获取目标卡包的模板名称"""
    if not self.target_pack:
        return None
    # 使用新的路径格式: packs_auto/{booster_name}
    booster_name = normalize_name_str(self.target_pack["booster_name"])
    return f"packs_auto/{booster_name}"
```

3. **可选：添加模板加载接口到 TemplateMatcher**:
```python
# 在 TemplateMatcher 类中添加
def load_single_template(self, file_path: Path) -> bool:
    """加载单个模板文件（供 PackImageManager 使用）"""
    return self._load_template_file(file_path, is_pack_template=True)
```

### 阶段 3: 测试工具改造 (Day 2-3)

#### 3.1 添加 debug_tool 测试命令
**文件**: `debug_tool.py`

**新增参数**:
```python
parser.add_argument(
    "--test-pack",
    type=str,
    metavar="ACTION",
    help="卡包测试模式: download|compare|match|batch",
)
parser.add_argument(
    "--booster",
    type=str,
    metavar="NAME",
    help="指定子包名称（如 Charizard,Mewtwo）",
)
parser.add_argument(
    "--interactive",
    action="store_true",
    help="交互式模式（用于裁剪 ROI 测试）",
)
```

#### 3.2 创建测试模块
**文件**: `src/ptcgp_auto/debug_tools/pack_tester.py`

**功能模块**:

1. **下载测试** (`download`):
```python
def test_download(booster_names: List[str]):
    """测试下载指定卡包图片"""
    manager = PackImageManager()
    for name in booster_names:
        success = manager.ensure_pack_ready(name)
        print(f"[{ '✓' if success else '✗' }] {name}")
```

2. **对比测试** (`compare`):
```python
def test_compare(booster_name: str):
    """对比公共图片与现有模板"""
    # 1. 下载公共图片
    # 2. 加载现有手动模板
    # 3. 显示两者尺寸和视觉对比
    # 4. 计算缩放比例建议
```

3. **裁剪测试** (`crop`):
```python
def test_crop_interactive(adb_controller, booster_name: str):
    """交互式测试裁剪参数"""
    # 1. 截图
    # 2. 显示当前处理后的图片效果
    # 3. 允许调整裁剪参数并实时预览
```

4. **匹配测试** (`match`):
```python
def test_match(adb_controller, booster_name: str, scale: float = None):
    """在设备上测试模板匹配效果"""
    # 1. 确保图片已下载处理
    # 2. 截图
    # 3. 尝试匹配模板
    # 4. 输出置信度和位置
    # 5. 如果没有指定 scale，自动扫描最佳比例
```

5. **批量测试** (`batch`):
```python
def test_batch(adb_controller, all_boosters: bool = False):
    """批量测试所有卡包"""
    # 1. 获取所有卡包列表
    # 2. 对每个卡包执行匹配测试
    # 3. 汇总结果报告
```

### 阶段 4: 设备测试与参数调优 (Day 3)

#### 4.1 连接设备执行测试

**步骤 1: 下载样本图片**
```bash
python debug_tool.py --test-pack download --booster Charizard,Mewtwo,Pikachu
```

**步骤 2: 对比分析**
```bash
python debug_tool.py --test-pack compare --booster Charizard
```

**步骤 3: 交互式确定 ROI**（如果需要调整）
```bash
python debug_tool.py -a 5755 --test-pack crop --booster Charizard --interactive
```

**步骤 4: 匹配测试**
```bash
# 自动扫描最佳缩放比例
python debug_tool.py -a 5755 --test-pack match --booster Charizard

# 或指定比例测试
python debug_tool.py -a 5755 --test-pack match --booster Charizard --scale 3.0
```

**步骤 5: 批量验证**
```bash
python debug_tool.py -a 5755 --test-pack batch --all
```

#### 4.2 参数调整

根据测试结果调整 `PackImageManager` 中的参数：
- `PACK_CROP_RATIO`: 如果公共图片边框过多
- `TARGET_WIDTH`: 如果匹配效果不佳

## 文件变更清单

### 新增文件
1. `src/ptcgp_auto_v2/utils/pack_image_manager.py` - 卡包图片管理器
2. `src/ptcgp_auto/debug_tools/pack_tester.py` - 卡包测试模块

### 修改文件
1. `src/ptcgp_auto_v2/infra/template.py` - 修改 `load_core_templates` 仅加载一级目录
2. `src/ptcgp_auto_v2/tasks/open_pack.py` - 集成 PackImageManager
3. `debug_tool.py` - 添加 `--test-pack` 参数支持
4. `.gitignore` - 添加 `templates/packs_auto/`

### 可选保留（过渡期）
- `templates/packs/` - 保留现有手动模板作为 fallback（如果需要）
- `src/ptcgp_auto/debug_tools/crop_pack.py` - 保留手动裁剪工具（如果需要）

## 验证检查点

- [ ] PackImageManager 能正确下载 WebP 并转换为 PNG
- [ ] 裁剪后的图片清晰度足够进行模板匹配
- [ ] 在 1080p 设备上匹配置信度 >= 0.8
- [ ] 在 2K/4K 设备上自动缩放后匹配正常
- [ ] 所有现有卡包都能成功匹配
- [ ] debug_tool 的测试命令工作正常

## 风险与回退方案

**风险**:
1. 公共图片分辨率较低 (160x256)，放大后可能模糊影响匹配
2. 宽高比可能与游戏内显示不一致

**回退方案**:
- 保留 `templates/packs/` 目录不删除
- 在 `PackImageManager` 添加 fallback 逻辑，如果公共图片处理失败，回退到手动模板
- 保留 `--crop-pack` 命令以备不时之需

## 后续优化

1. 添加缓存机制，避免重复下载
2. 支持增量更新（检查 GitHub 图片是否有更新）
3. 并行下载多个卡包图片
4. 添加图片质量验证（下载后检查清晰度）

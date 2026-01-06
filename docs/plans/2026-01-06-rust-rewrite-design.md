# PTCGP Auto Rust 重写设计

## 概述

将 Python 版本的 PTCGP 自动化脚本重写为 Rust，以获得更好的性能和更便捷的分发。

## 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| OCR | rust-paddle-ocr | 跨平台，GPU 加速，多语言支持 |
| ADB | adb_client | 纯 Rust，满足点击/截图/滑动需求 |
| 图像处理 | imageproc | 纯 Rust，零外部依赖 |
| 模型加载 | 单语言 + 自动下载 | 首次运行时下载到本地缓存 |
| 并发模型 | 同步阻塞 | 简单直接，符合顺序执行逻辑 |

## 依赖

```toml
[dependencies]
ocr-rs = { git = "https://github.com/zibo-chen/rust-paddle-ocr.git", branch = "next" }
adb_client = "0.11"
image = "0.25"
imageproc = "0.26"
clap = { version = "4", features = ["derive"] }
serde = { version = "1", features = ["derive"] }
toml = "0.8"
anyhow = "1"
thiserror = "1"
ureq = "2"
sha2 = "0.10"
dirs = "5"
```

## 项目结构

```
ptcgp-auto-rs/
├── Cargo.toml
├── models.toml              # 模型清单（编译时内嵌）
├── src/
│   ├── main.rs              # 入口 + CLI
│   ├── lib.rs               # 库导出
│   ├── adb.rs               # ADB 控制器
│   ├── ocr.rs               # OCR 引擎封装
│   ├── model_manager.rs     # 模型下载/缓存管理
│   ├── recognizer.rs        # 模板匹配 + 颜色检测
│   ├── page_detector.rs     # 页面识别
│   ├── action/              # 动作模块
│   │   ├── mod.rs
│   │   ├── base.rs
│   │   ├── battle.rs
│   │   └── ...
│   ├── state.rs             # 状态管理
│   └── config.rs            # 配置定义
├── config/                  # 配置文件
│   ├── zh_Hant.toml
│   └── en_US.toml
└── templates/               # 按钮模板图片
```

## 核心模块接口

### ADB 控制器 (`adb.rs`)

```rust
pub struct AdbController {
    device: AdbDevice,
    screen_size: (u32, u32),
}

impl AdbController {
    pub fn connect(host: &str, port: u16) -> Result<Self>;
    pub fn screenshot(&self) -> Result<DynamicImage>;
    pub fn tap(&self, x: u32, y: u32) -> Result<()>;
    pub fn tap_center(&self, rect: Rect) -> Result<()>;
    pub fn swipe(&self, from: (u32, u32), to: (u32, u32), duration_ms: u32) -> Result<()>;
    pub fn swipe_up(&self, ratio: f32) -> Result<()>;
    pub fn swipe_down(&self, ratio: f32) -> Result<()>;
    pub fn back(&self) -> Result<()>;
}
```

### OCR 引擎 (`ocr.rs`)

```rust
pub struct OcrEngine {
    engine: ocr_rs::OcrEngine,
    language: Language,
}

pub enum Language {
    ZhHant,
    EnUS,
    Korean,
}

impl OcrEngine {
    pub fn new(language: Language, model_paths: ModelPaths) -> Result<Self>;
    pub fn recognize(&self, image: &DynamicImage) -> Result<Vec<OcrResult>>;
}

pub struct OcrResult {
    pub text: String,
    pub bbox: Rect,
    pub confidence: f32,
}
```

### 模型管理器 (`model_manager.rs`)

```rust
pub struct ModelManager {
    cache_dir: PathBuf,
    manifest: ModelsManifest,
}

impl ModelManager {
    pub fn new() -> Result<Self>;
    pub fn ensure_models(&self, language: Language) -> Result<ModelPaths>;
}
```

模型清单在编译时内嵌。模型文件在首次使用时运行时下载到 `~/.cache/ptcgp-auto/models/`。

### 识别器 (`recognizer.rs`)

```rust
pub struct Recognizer {
    ocr: OcrEngine,
    templates: HashMap<String, GrayImage>,
    screen_size: (u32, u32),
}

impl Recognizer {
    pub fn new(ocr: OcrEngine, templates_dir: &Path) -> Result<Self>;
    pub fn find_text(&self, image: &DynamicImage, pattern: &str) -> Option<Rect>;
    pub fn find_text_variants(&self, image: &DynamicImage, patterns: &[&str]) -> Option<Rect>;
    pub fn find_template(&self, image: &DynamicImage, name: &str) -> Option<Rect>;
    pub fn check_color_ratio(&self, image: &DynamicImage, region: Rect, hsv_range: HsvRange) -> f32;
    pub fn check_state(&self, image: &DynamicImage, state: &str) -> Option<bool>;
}
```

## 配置格式

```toml
# config/zh_Hant.toml

[ocr]
language = "zh_Hant"
recognition_level = "accurate"

[screen]
width = 1080
height = 1920
template_base_width = 1080

[timing]
wait_after_click_ms = 500
wait_page_transition_ms = 1500
wait_battle_check_interval_ms = 5000
wait_battle_timeout_ms = 600000

[battle]
levels = ["elite", "intermediate", "beginner"]
auto_enable_auto_battle = true

[[pages]]
name = "home"
priority = 10
action = "go_solo_battle"
identifiers = [{ type = "text", patterns = ["單人對戰", "单人对战"] }]

[[pages]]
name = "battle_result"
priority = 100
action = "click_next"
identifiers = [{ type = "template", name = "battle_next_btn" }]

[text_patterns]
auto = ["自動", "Auto", "自动"]
next = ["下一步", "Next", "繼續"]
ok = ["OK", "確認", "确认"]
```

## 主循环

```rust
impl PtcgpAuto {
    pub fn run(&mut self) -> Result<()> {
        let mut no_action_count = 0;

        loop {
            let screenshot = self.adb.screenshot()?;

            match self.detect_page(&screenshot) {
                Some((page_name, page_config, match_info)) => {
                    no_action_count = 0;
                    println!("[页面] {}", page_name);
                    self.action_handler.execute(&page_config.action, &screenshot, &match_info)?;
                    sleep(self.config.timing.wait_page_transition());
                }
                None => {
                    no_action_count += 1;
                    if no_action_count >= 5 {
                        println!("无法识别页面，可能需要手动干预");
                        no_action_count = 0;
                    }
                    sleep(self.config.timing.wait_battle_check_interval());
                }
            }
        }
    }
}
```

## 命令行接口

```rust
#[derive(Parser)]
#[command(name = "ptcgp-auto")]
struct Cli {
    /// ADB 连接地址（host:port 或仅 port）
    #[arg(short, long, default_value = "127.0.0.1:5555")]
    address: String,

    /// 界面语言
    #[arg(short, long, default_value = "zh_Hant")]
    language: String,

    /// 禁用对战中自动开启自动对战
    #[arg(long)]
    no_auto_battle: bool,
}
```

## 关键特性

1. **零外部依赖安装** - 纯 `cargo build`，模型自动下载
2. **跨平台** - macOS/Linux/Windows，GPU 后端自动选择
3. **多语言配置** - TOML 配置文件，易于扩展新语言
4. **与 Python 版本兼容** - 相同的模板图片、相同的状态文件格式

# Technology Stack

**Analysis Date:** 2026-02-23

## Languages

**Primary:**
- Python 3.12 - Main application logic, automation, ML inference, web backend

**Secondary:**
- JavaScript (ES6 Modules) - Frontend interactivity (no build system, native ES modules)
- Jinja2 Templates - Server-side HTML rendering

## Runtime

**Environment:**
- Python 3.12 (managed via `.python-version`)
- Platform: **macOS only** (required for Apple Vision Framework OCR)

**Package Manager:**
- uv (implied by `pyproject.toml` structure with `[dependency-groups]`)
- Lockfile: Not detected (relies on pyproject.toml)

## Frameworks

**Core:**
- FastAPI 0.128+ - Web API framework
- SQLModel 0.0.16+ - ORM layer (SQLAlchemy + Pydantic hybrid)
- Uvicorn 0.40+ - ASGI server

**Machine Learning:**
- Ultralytics 8.3+ - YOLO object detection for card recognition
- CoreMLTools 9.0+ - CoreML model conversion (Apple Silicon optimized)
- Apple Vision Framework (via pyobjc-framework-vision) - OCR engine

**Automation:**
- uiautomator2 3.5+ - Android device control via ADB

**Frontend:**
- Jinja2 3.1+ - Server-side templating
- HTMX - AJAX/dynamic updates without SPA complexity

**Logging:**
- Loguru 0.7+ - Structured logging with intercept capability

## Key Dependencies

**Critical:**
- `opencv-python` 4.8+ - Image processing, perspective transforms
- `pillow` 10.0+ - Image manipulation
- `scipy` 1.17+ - DCT for perceptual hash (100-1000x faster than pure Python)
- `numpy` 1.14.5-2.3.5 - Numerical operations
- `pyobjc-framework-vision` 10.0+ - macOS Vision framework bindings

**Infrastructure:**
- `requests` - HTTP client (webhook notifications, model downloads)
- `python-multipart` - Form data handling
- `questionary` 2.0+ - Interactive CLI prompts

## Configuration

**Environment:**
- `.env` file for runtime configuration
- `pyproject.toml` for dependency management
- `.python-version` for Python version pinning

**Build:**
- No build system required (Python + native ES modules)

**Key Config Files:**
- `src/ptcgp_auto_v2/config/settings.py` - Runtime settings (dataclass-based)
- `src/ptcgp_auto_v2/config/constants.py` - Application constants

## Platform Requirements

**Development:**
- macOS (Darwin) - Required for Apple Vision Framework OCR
- BlueStacks Air - Android emulator for game automation
- ADB (Android Debug Bridge) - Device communication

**Production:**
- Same as development (macOS-only deployment)
- SQLite database file in `data/ptcgp_v2.db`

## Sub-projects

**yolo-card-training:**
- Location: `yolo-card-training/`
- Purpose: YOLO model training pipeline
- Separate pyproject.toml with training-specific dependencies

---

*Stack analysis: 2026-02-23*

#!/usr/bin/env python3
"""
批量下载 sample-images 背景图片
使用 GitHub Pages 直接链接（比 ZIP 更快）
"""

import urllib.request
from pathlib import Path
from tqdm import tqdm

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "raw" / "backgrounds"


def download_backgrounds(start=1, end=100):
    """下载背景图片（默认前 100 张）"""
    print(f"📥 下载 sample-images 背景图片 ({start}-{end})...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    for i in tqdm(range(start, end + 1), desc="下载"):
        url = f"https://yavuzceliker.github.io/sample-images/image-{i}.jpg"
        output_path = OUTPUT_DIR / f"background_{i:04d}.jpg"

        if output_path.exists():
            continue

        try:
            urllib.request.urlretrieve(url, output_path)
            downloaded += 1
        except Exception:
            pass

    print(f"✅ 已下载 {downloaded} 张背景图片到 {OUTPUT_DIR}")


if __name__ == "__main__":
    download_backgrounds(1, 50)  # 下载 50 张背景

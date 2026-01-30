# YOLO 卡牌检测模型训练

## 说明

这是一个**完全独立**的训练子项目，用于生成 YOLO 卡牌检测模型。

## 使用方式

```bash
cd yolo-card-training
# direnv 会自动加载环境，或手动执行：
source .venv/bin/activate

# 1. 下载素材
python scripts/download_assets.py

# 2. 生成数据集
python scripts/generate_dataset.py --num-images 10000

# 3. 训练模型
python scripts/train.py --epochs 100 --device mps
```

## 输出

训练好的模型：`output/models/best.pt`

## 注意

- 数据和模型文件被 gitignored，不会提交到仓库
- 本项目完全不依赖主项目代码

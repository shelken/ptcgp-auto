# 卡牌预览修复清单（2026-03-27）

## 已修问题

1. 拖拽时卡牌抖动/翻转不稳定  
设计/实现文件：  
- `src/ptcgp_auto_v2/web/frontend/src/hooks/use-card-preview-drag.ts`

2. 预览进场时原位置仍显示原卡（双卡并存）  
设计/实现文件：  
- `src/ptcgp_auto_v2/web/frontend/src/pages/records-page.tsx`  
- `src/ptcgp_auto_v2/web/frontend/src/pages/owned-cards-page.tsx`  
- `src/ptcgp_auto_v2/web/frontend/src/styles/records-layout.css`

3. 主题色提取未使用真实图像（仅伪色）  
设计/实现文件：  
- `src/ptcgp_auto_v2/web/frontend/src/lib/card-theme-color.ts`

4. 主题色双引擎对比缺失（`fast-average-color` / `node-vibrant`）  
设计/实现文件：  
- `src/ptcgp_auto_v2/web/frontend/src/lib/card-theme-color.ts`（新增 benchmark 与推荐规则）

## 双引擎结论（本次实测）

- 样本：40 张卡图  
- 推荐引擎：`fast-average-color`  
- 原因：P95 更低（满足优先规则）

## 验证

- `bun run build` 通过  
- `uv run ruff check src` 通过

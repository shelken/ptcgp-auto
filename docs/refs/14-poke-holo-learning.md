# 14 - poke-holo 页面学习笔记

## 一句话结论
- `poke-holo.simey.me` 的核心不是单一动画，而是“统一变量驱动 + 分层光效 + 稀有度规则映射”。

## 关键实现点（可直接迁移）
- 交互统一变量：先把指针换算成 `percent/center`，再统一写入 `--pointer-* / --rotate-* / --background-* / --card-opacity`，所有层只消费变量。  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/src/lib/components/Card.svelte
- 交互更新节流：高频 `pointermove` 只在 `requestAnimationFrame` 内提交一次 spring 更新，避免事件风暴。  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/src/lib/components/Card.svelte
- 回弹策略：结束交互后统一把旋转、光位、透明度缓回中位，避免残留姿态。  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/src/lib/components/Card.svelte
- 分层结构：`translater -> rotator -> front -> shine(+before/after) -> glare`，位移/旋转与光效层解耦。  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/src/lib/components/Card.svelte  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/public/css/cards/base.css
- 稀有度插件化：通过 `data-rarity / data-subtypes / data-supertype` 命中不同效果样式文件，而不是改交互代码。  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/src/lib/components/CardProxy.svelte  
  来源: https://github.com/simeydotme/pokemon-cards-css/tree/main/public/css/cards
- Holo 典型层：`regular-holo` 用重复渐变+扫描线+clip-path；`cosmos` 用多纹理层；`rainbow/secret` 用高密度彩带+glitter+强 blend。  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/public/css/cards/regular-holo.css  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/public/css/cards/cosmos-holo.css  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/public/css/cards/rainbow-holo.css  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/public/css/cards/secret-rare.css
- 裁剪规则：用 `clip-path` 把 holo/glare 限制到卡图窗，stage/trainer 使用不同裁剪形状。  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/public/css/cards.css  
  来源: https://github.com/simeydotme/pokemon-cards-css/blob/main/public/css/cards/base.css

## 与我们当前问题的直接对应
- “看起来只平移不旋转”：要先保证入场轨迹与卡内旋转是两条独立链路，不能互相覆盖。
- “光效不明显”：要按 rarity 命中不同效果层，不能只有一套固定亮斑。
- “边缘分层感强”：层与主图必须同几何基准（同圆角、同裁剪、同坐标空间），避免错层。
- “GPU 高占用”：交互更新必须 rAF 合帧，静置时停帧，禁止无意义逐帧写样式。

## 页面与仓库
- Demo: https://poke-holo.simey.me/
- 仓库: https://github.com/simeydotme/pokemon-cards-css


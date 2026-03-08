# HRW 单参数激进度设计

## 背景

当前 `hrw_progress_balance` 公开暴露了多个数值参数：

- `PACK_AUTO_HRW_PROGRESS_BETA`
- `PACK_AUTO_HRW_WEIGHT_MIN`
- `PACK_AUTO_HRW_WEIGHT_MAX`
- `PACK_AUTO_HRW_LOAD_EPSILON`

这会带来两个问题：

1. 人工调参没有清晰边界，不容易判断何时“调到头”。
2. 公开参数过多，实际语义重叠，难以稳定控制“缺少的包要分配更多”这一目标。

## 目标

- 将 HRW 的人工可调参数收敛为一个 `0.0 ~ 1.0` 的单一参数。
- `constants.py` 中清晰区分“可调参数”和“内部固定参数”。
- 让 `1.0` 代表明显偏激进的极限值，而不是略高于当前默认值。
- 尽量复用现有 HRW 计算框架，降低回归风险。

## 方案选择

采用单一公开参数 `PACK_AUTO_HRW_AGGRESSIVENESS`，内部派生 HRW 所需的强度参数。

不采用仅将 `beta` 单位化的方案，因为该方案仍然会受到 `weight_max` 与 `epsilon` 的隐式限制，表面只有一个旋钮，实际上仍然是多参数耦合。

## 公开参数

### HRW 可调参数

- `PACK_AUTO_HRW_AGGRESSIVENESS`
  - 范围：`0.0 ~ 1.0`
  - 语义：数值越大，越优先将账号分配给高稀有度进度缺口更大的子包

### 建议语义区间

- `0.0 ~ 0.3`：保守
- `0.3 ~ 0.6`：常规
- `0.6 ~ 0.8`：激进
- `0.8 ~ 1.0`：极激进

## 内部派生规则

为了让 `1.0` 真正代表“极激进”而不是略高于当前线性方案，改用指数权重模型，并通过二次映射派生内部参数：

```python
effective_scale = 6.0 * aggressiveness * aggressiveness
effective_weight_max = math.exp(effective_scale)
effective_epsilon = 4.0 * aggressiveness * aggressiveness
```

关键点：

- `aggressiveness = 0.0`
  - `scale = 0.0`
  - `weight_max = 1.0`
  - `epsilon = 0.0`
  - 表现接近平均分配
- `aggressiveness = 0.5`
  - `scale = 1.5`
  - `weight_max ≈ 4.482`
  - `epsilon = 1.0`
  - 比旧版 `0.5` 更偏向缺口包，但仍明显低于极激进档
- `aggressiveness = 1.0`
  - `scale = 6.0`
  - `weight_max ≈ 403.429`
  - `epsilon = 4.0`
  - 会显著集中到最低进度包，满足极激进档目标

## 逻辑调整

### 权重计算

使用指数缺口权重模型放大高缺口包之间的差距：

```python
weight = math.exp(effective_scale * gap)
```

### 删除无效调参面

移除 `PACK_AUTO_HRW_WEIGHT_MIN`。

原因：

- 当前指数权重公式中 `gap` 范围为 `0.0 ~ 1.0`
- `weight = math.exp(effective_scale * gap)` 的最小值始终为 `1.0`
- 现有 `weight_min` 实际不会生效，属于无意义公开参数

### 缓存键

HRW 快照缓存键不再直接拼接旧参数，而是改为：

- `PACK_AUTO_HRW_AGGRESSIVENESS`
- 派生后的 `effective_scale`
- 派生后的 `effective_weight_max`
- 派生后的 `effective_epsilon`
- 其他仍影响结果的固定常量

这样既保留缓存一致性，也避免公开参数与内部实现脱节。

## constants.py 组织方式

在 HRW 相关区域拆分两个分组：

1. `HRW 可调参数`
2. `HRW 内部固定参数`

其中仅第一组允许人工日常调节；第二组通过注释明确说明“不建议外部直接调整”。

## 脚本与测试同步

### 模拟脚本

`scripts/simulate_hrw_pack_distribution.py` 需要同步调整：

- 输出公开参数 `PACK_AUTO_HRW_AGGRESSIVENESS`
- 输出派生后的 `scale / weight_max / epsilon`
- 不再输出已移除的 `weight_min`

### 测试

需要覆盖以下点：

1. `aggressiveness` 派生结果正确
2. `aggressiveness=0.0` 时更接近平均分配
3. `aggressiveness=1.0` 时对低进度包偏置更强
4. 现有稳定性测试继续成立
5. 模拟脚本直接复用正式常量，避免参数漂移

## 风险

- `1.0` 对应的内部强度显著提高，分配结果会比当前更集中，需要通过测试确认不会破坏稳定性预期。
- 当前数据库初始化存在与 `accounts.exchange_points` 相关的迁移问题，可能影响真实脚本运行验证；单元测试应覆盖主要逻辑，避免完全依赖本地数据库状态。

## 实施范围

- `src/ptcgp_auto_v2/config/constants.py`
- `src/ptcgp_auto_v2/utils/pack_auto_selector.py`
- `scripts/simulate_hrw_pack_distribution.py`
- `src/ptcgp_auto_v2/tests/utils/test_pack_auto_selector.py`
- `src/ptcgp_auto_v2/tests/utils/test_simulate_hrw_pack_distribution.py`

- 编写代码前，先阅读一次项目根目录的`AGENTS.md`

### 数据访问与状态原则

- **任务状态禁止存 ORM**：`state`、实例属性、跨页面缓存里只允许放 `id`、标量和 `dataclass` 纯数据，禁止放 `Account/Card/Request/TaskInstance` 这类 ORM 实体
- **任务内事务边界单一**：需要访问数据库时，在当前业务动作内显式 `with session_scope() as session:`，需要多个 Repository 时统一 `RepositoryFactory(session)`
- **任务辅助函数返回纯数据**：`tasks/utils`、任务私有 helper 返回 `dataclass` 纯数据或标量，禁止返回带 Session 生命周期的 ORM
- **任务完成写库后立即结束事务**：不要把查出的 ORM 带到页面处理循环外继续使用，需要时重新开事务按 `id` 查询

### 页面内处理原则

- **完整处理**：使用 pages 规则匹配到处理函数时，必须在同一段逻辑内完成该页面所有操作（包括弹窗），然后通过 close/back 返回主界面，让 page 规则重新匹配
- **禁止硬编码**：页面处理中不允许直接匹配语言文本，必须使用 locale 配置，以 zh_Hant 为基准，调用 `get_text_patterns()` 获取
- **pages 注释原则**：每个页面规则块前必须添加中文注释，写上 `zh_Hant.py` 中该 key 的 value 值
  ```python
  # 商店 / 得卡挑戰
  {
      "name": "game_home_main",
      "identifiers": get_text_patterns("game_home_main"),
      ...
  }
  ```
- **精确匹配**：需要精确匹配或点击文字时，必须设置 `exact=True`
- **action_cache**：使用 dict 记录页面内已完成操作，避免重复执行
- **优先级规则**：pages 规则数字越小越优先匹配
- **位置选择**：匹配文本时选择中间位置，避免四角（可能被遮挡）

### 页面分发原则（禁止反模式）

- **handle_page 纯分发**：只按页面名平级分发，所有 handler 平级，禁止用业务状态拦截
  ```python
  # ❌ 错误：用 status 拦截
  if request.status == "sending":
      return self._handle_sending_pages(page_name, page_info)
  
  # ✅ 正确：平级分发
  handlers = {
      "exchange_page_main": self._handle_exchange_page_main,
      "exchange_waiting_page": self._handle_waiting_page,
  }
  ```
- **状态仅用于页面内**：业务状态只能在具体 handler 内部读取，决定"这个页面里点击什么"
- **绝对不能**：用状态决定"这个页面能不能处理"

### 开包流程规范

- **开包识别编排原则**：`_recognize_cards` 只做流程编排，`DetectedCard -> Card/批次dict` 映射统一放 `tasks/utils`
- **开包结果纯数据原则**：识别映射、通知、入库前整理统一使用纯数据结构，禁止把 `Card/CardSet/Pack` ORM 带出事务
- **识别查询去重原则**：同一批识别结果的卡牌详情只查一次并复用（入库与通知共用）
- **高稀有度保存与通知同入口原则**：稀有度通知必须绑定在 `high_rarity_saver.py` 保存流程内触发
- **识别映射统一结构原则**：`DetectedCard` 映射统一走 `pack_result_mapper.py::map_detected_cards`
- **结果行归并分层原则**：结果页行签名、归并、分包统一放 `pack_result_rows.py`，不要继续塞回 mapper
- **通知配置归 Notifier 原则**：task 层不做通知过滤，由 `Notifier.notify_rare_card` 内部配置决定
- **稀有卡事件来源标记原则**：调用 `save_high_rarity_cards` 时必须传入中文来源消息（如"开包获得稀有卡牌"）

### PackOpeningTaskBase 规范

- **继承原则**：涉及开包流程的任务（open_pack、claim_gifts、init_account）必须继承 `PackOpeningTaskBase`
- **禁止重复实现**：禁止在各任务中重复实现开包页面处理、卡牌识别、记录保存逻辑
- **必须实现的扩展点**：
  - `get_pack_record_type()`: 返回 pack 记录类型（如 "daily_free"）
  - `get_rare_card_notify_message()`: 返回中文来源消息（如 "开包获得稀有卡牌"）
- **可选扩展点**：
  - `get_target_pack_context()`: 返回目标卡包上下文（注意：open_pack 显式目标优先于推断上下文）
  - `should_prepare_pack_resources()`: 是否需要准备卡包图片资源（默认 False）
  - `get_fixed_set_code()`: 固定系列代码
  - `finalize_pack_session()`: 任务结束时调用，清理推断会话
- **子包推断规则**：
  - **两阶段策略**：第一阶段（滑动页）模板匹配优先；第二阶段（结果页）卡牌反推兜底
  - **PROMO 排除**：`exclude_promo=True` 时排除 PROMO 系列干扰，但普通系列缺失 Hash 仍可下载
  - **上下文优先级**：`fixed_set_code > explicit_target.set_code > inferred_context.set_code > None`
  - **模板名规范化**：使用 `normalize_name_str()` 处理 pack.name 后再拼模板路径
  - **会话清理**：落库成功后（包括异常路径）必须调用 `_clear_pack_inference_session()` 卸载动态模板
- **禁止反模式**：
  ```python
  # ❌ 错误：覆盖基类方法
  def _recognize_cards(self): ...
  
  # ❌ 错误：英文 pack_type 拼接
  notify_message = f"{self.get_pack_record_type()}获得稀有卡牌"
  
  # ✅ 正确：通过扩展点提供纯中文消息
  def get_rare_card_notify_message(self):
      return "开包获得稀有卡牌"
  ```

### 测试规范

- **任务测试优先级原则**：新增/重构 task 时，优先补"核心分支 + 去重/幂等 + 边界输入"三类测试
- **工具函数单测**：纯工具函数（如 friend_id/nickname 提取）必须补独立单测

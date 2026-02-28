- 编写代码前，先阅读一次项目根目录的`AGENTS.md`
- 页面内处理原则，当使用pages的规则匹配到某个函数来处理时，我们通常的做法是，完成这个页面的所有逻辑，例如某个页面需要点击多个位置和进行各种操作，当点击某个选框，他会弹出界面，因此在我们点击选框之后，需要在这个if段里面把这个弹出界面的逻辑完成，之后点击某个close或者back等返回操作回到当前页面的主界面，以让page规则重新匹配到这个页面，而不是陷入当前页面的子页面出不去。而子页面完成之后只需要改变对应的某个变量作为完成的标志来判断是否重新这个if段。
- 每个页面的处理中，不允许直接出现对某个语言的匹配、硬编码文本，必须在 locale 中定义对应文本，一切以 zh_Hant 为为基准，调用get_text_patterns来获取对应值。
- **pages 注释原则**：每个页面规则块前必须添加对应的中文注释，写上 `zh_Hant.py` 中该 key 的 value 值，便于快速理解页面识别逻辑
  ```python
  # 商店 / 得卡挑戰
  {
      "name": "game_home_main",
      "identifiers": get_text_patterns("game_home_main"),
      ...
  }
  ```
- 当说明需要精确匹配，或者精确点击文字的时候，必须确保 exact=True，防止点击到其他包含的元素
- 应该使用一个dict，来存储当前已经点击是否完成哪些内容，如果点击了/操作了，不应该进入相同页面的时候再次点击/操作，而不是处于什么阶段，阶段应该是不同页面流转的处理，相同页面内应该用dict记录是否完成了哪个操作
- 目前要寻找不同语言的某个值统一使用get_text_patterns("key")来获取不同语言的文本
- pages 规则数字越小越优先匹配
- pages 规则匹配文本时，不要选取左上角的文本来作为匹配项。尽量选择中间而不是四角，因为会有文本被阻挡的可能。
- **开包识别编排原则**：`open_pack` 里的 `_recognize_cards` 只做流程编排；`DetectedCard -> Card/批次dict` 映射统一放 `tasks/utils`，避免任务类继续膨胀。
- **识别查询去重原则**：同一批识别结果的卡牌详情只查一次并复用（入库与通知共用），禁止在一个流程里重复查库。
- **高稀有度保存与通知同入口原则**：`open_pack` / `wonder_pick` 的稀有度通知必须绑定在 `tasks/utils/high_rarity_saver.py` 保存流程内触发，禁止“保存一处、通知一处”的分离实现；仅高稀有度且满足任务条件（如 wonder_pick 命中目标稀有度）才通知。
- **识别映射统一结构原则**：`DetectedCard` 映射统一走 `tasks/utils/pack_result_mapper.py::map_detected_cards`，返回单一 rows 结构（含 card_obj + 各类字段），任务内禁止再拆两份结构或重复写循环映射。
- **通知配置归 Notifier 原则**：task 层（含 wonder_pick）不做通知过滤判断，是否发送通知由 `Notifier.notify_rare_card` 内部配置决定。
- **稀有卡事件来源标记原则**：task 调用 `save_high_rarity_cards` 时必须传入来源消息（如“开包获得稀有卡牌”/“得卡挑战获得稀有卡牌”），由 notifier 正文统一展示事件来源。
- **任务测试优先级原则**：新增/重构 task 时，优先补“核心分支 + 去重/幂等 + 边界输入”三类测试；纯工具函数（如 friend_id/nickname 提取）必须补独立单测，避免仅靠任务集成间接覆盖。

### 页面优先原则（禁止反模式）
**致命错误示例**：在 `handle_page` 中先检查 `request.status` 再决定页面分发
```python
# ❌ 错误：用业务状态拦截页面分发
if request.status == "sending":
    return self._handle_sending_pages(page_name, page_info)  # 里面只有部分页面
elif request.status == "sended":
    return self._handle_sended_pages(page_name, page_info)   # waiting_page 在这里
```
**后果**：页面匹配到了（如 `exchange_waiting_page`），但因为 status 是 sending，被拦截进不去对应的处理器。

**正确做法**：
```python
# ✅ 正确：handle_page 只按页面名纯分发，所有页面 handler 平级
handlers = {
    "exchange_page_main": self._handle_exchange_page_main,
    "exchange_waiting_page": self._handle_waiting_page,  # 不限制 status
    "exchange_choose_friend": self._handle_choose_friend,
    # ... 所有页面平级
}
handler = handlers.get(page_name)
if handler:
    return handler(page_info)
```

### 状态只用于页面内逻辑，不用于页面路由
- **业务状态**（如 `request.status = sending/sended`）**只能**在具体的页面 handler 内部读取，用于决定"这个页面里点击什么/执行什么操作"
- **绝对不能**用状态来决定"这个页面能不能处理"
- 参考正确实现：`open_pack.py`, `manage_friendship.py` 的 `handle_page` 写法

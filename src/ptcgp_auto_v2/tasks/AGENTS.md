- 页面内处理原则，当使用pages的规则匹配到某个函数来处理时，我们通常的做法是，完成这个页面的所有逻辑，例如某个页面需要点击多个位置和进行各种操作，当点击某个选框，他会弹出界面，因此在我们点击选框之后，需要在这个if段里面把这个弹出界面的逻辑完成，之后点击某个close或者back等返回操作回到当前页面的主界面，以让page规则重新匹配到这个页面，而不是陷入当前页面的子页面出不去。而子页面完成之后只需要改变对应的某个变量作为完成的标志来判断是否重新这个if段。
- 每个页面的处理中，不允许直接出现对某个语言的匹配、硬编码文本，必须在 locale 中定义对应文本，一切以 zh_Hant 为为基准，调用get_text_patterns来获取对应值。
- 当说明需要精确匹配，或者精确点击文字的时候，必须确保 exact=True，防止点击到其他包含的元素
- 应该使用一个dict，来存储当前已经点击是否完成哪些内容，如果点击了/操作了，不应该进入相同页面的时候再次点击/操作，而不是处于什么阶段，阶段应该是不同页面流转的处理，相同页面内应该用dict记录是否完成了哪个操作
- 目前要寻找不同语言的某个值统一使用get_text_patterns("key")来获取不同语言的文本
- pages 规则数字越小越优先匹配
- 每次遇到新问题并解决了，必须把正确方式写回下面的常见问题与注意点，简洁点，直接告诉问题和正确做法。

## 【2026-02-15 新增】任务编写核心原则

### 1. 页面优先原则（禁止反模式）
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

### 2. 状态只用于页面内逻辑，不用于页面路由
- **业务状态**（如 `request.status = sending/sended`）**只能**在具体的页面 handler 内部读取，用于决定"这个页面里点击什么/执行什么操作"
- **绝对不能**用状态来决定"这个页面能不能处理"
- 参考正确实现：`open_pack.py`, `manage_friendship.py` 的 `handle_page` 写法

### 3. 反模式总结（本次踩坑记录）
| 反模式 | 错误表现 | 正确做法 |
|-------|---------|---------|
| 状态拦截路由 | `if status == sending: handle_sending_pages()` 导致 waiting_page 进不去 | 所有页面 handler 平级注册，不检查 status |
| 状态决定页面可见性 | 认为 "sending 状态不应该看到 waiting_page" | 页面可见性只由实际游戏画面决定，status 只影响操作选择 |
| 在路由层做业务判断 | `handle_page` 里判断 "如果 status=X 且 page=Y 则..." | 路由层只分发，业务判断下沉到具体 handler |

### 4. 任务编写 checklist
写新 task 前必须检查：
- [ ] `handle_page` 是**纯页面分发**，没有 `if status == xxx` 拦截
- [ ] 所有 pages 规则里的页面都在 handlers 字典中有对应 handler
- [ ] status/request 状态**只在**具体 handler 内部读取，用于决定操作（点哪个按钮/走哪条分支）
- [ ] 参考现有正确实现：`open_pack.py` 的 handle_page 是标准写法

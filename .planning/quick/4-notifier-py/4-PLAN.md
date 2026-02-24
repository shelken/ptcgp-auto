---
phase: quick-4-notifier-py
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/ptcgp_auto_v2/infra/notifier.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "所有公共方法签名保持不变"
    - "通知功能完全不变"
    - "代码行数减少约 20%"
  artifacts:
    - path: src/ptcgp_auto_v2/infra/notifier.py
      provides: 简化后的通知器模块
  key_links:
    - from: 外部调用方
      to: Notifier 公共方法
      via: 方法签名
      pattern: "notify_rare_card|notify_task_status|notify_system_warning"
---

<objective>
重构并简化 notifier.py，保持功能不变，代码简洁优雅。

Purpose: 减少静态方法、内联简单辅助方法、消除过度抽象
Output: 更简洁易读的 Notifier 类（约 320 行）
</objective>

<execution_context>
@/Users/shelken/.config/opencode/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
当前文件有 441 行，包含 9 个 @staticmethod 方法，其中大部分可以内联：

**待内联/简化的静态方法：**
1. `_format_now()` - 单行，内联到调用处
2. `_is_rare_card_notifiable()` - 单行判断，内联
3. `_is_task_status_notifiable()` - 仅一处调用，内联
4. `_build_system_warning_content()` - 仅一处调用，内联
5. `_build_webhook_payload()` - 简单 dict 构建，内联

**保留的方法：**
1. `_resolve_webhook_url()` - 初始化逻辑，保留但可简化
2. `_resolve_account_name()` - 两处调用，保留
3. `_build_rare_card_content()` - 保留，格式化逻辑较清晰
4. `_build_task_status_content()` - 保留，格式化逻辑较清晰
5. `_resolve_card_image_url()` - 保留，逻辑独立

**不变的内容：**
- 所有公共方法签名
- 全局 `_notifier_instance` 和 `get_notifier()` 函数
- 导入语句
</context>

<tasks>

<task type="auto">
  <name>内联单行/单次使用的静态方法</name>
  <files>src/ptcgp_auto_v2/infra/notifier.py</files>
  <action>
重构 Notifier 类，执行以下简化：

1. **删除并内联 `_format_now()`**：
   - 将 `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` 直接内联到 `notify_task_status()` 和 `notify_system_warning()` 调用处

2. **删除并内联 `_is_rare_card_notifiable()`**：
   - 在 `notify_rare_card()` 中直接使用 `card_id in notify_card_ids or rarity in notify_by_rarity`

3. **删除并内联 `_is_task_status_notifiable()`**：
   - 在 `notify_task_status()` 中直接内联判断逻辑，保留 logger.debug

4. **删除并内联 `_build_system_warning_content()`**：
   - 在 `notify_system_warning()` 中直接构建 content 字符串

5. **删除并内联 `_build_webhook_payload()`**：
   - 在 `_send_webhook()` 中直接构建 payload dict

6. **简化 `_resolve_webhook_url()`**：
   - 转为普通实例方法或保持静态但移除不必要的参数命名

确保：
- 所有公共方法签名不变
- 所有功能逻辑不变
- 删除不再使用的静态方法
- 更新模块注释说明变更
  </action>
  <verify>
```bash
# 语法检查
python -m py_compile src/ptcgp_auto_v2/infra/notifier.py

# 行数检查（目标 < 380 行）
wc -l src/ptcgp_auto_v2/infra/notifier.py
```
  </verify>
  <done>
- 文件语法正确
- 行数减少约 20%
- 所有公共方法签名保持不变
- 无静态方法调用错误
  </done>
</task>

<task type="auto">
  <name>验证重构后功能完整性</name>
  <files>src/ptcgp_auto_v2/infra/notifier.py</files>
  <action>
运行相关测试确保功能不变：

```bash
# 运行 notifier 相关测试
PYTHONPATH=src python -m pytest tests/ -k notifier -v --tb=short 2>/dev/null || echo "无专门测试，继续"

# 运行 web 相关测试（使用 notifier）
PYTHONPATH=src python -m pytest src/ptcgp_auto_v2/web/tests/ -v --tb=short 2>/dev/null || echo "无 web 测试"

# 导入测试
PYTHONPATH=src python -c "from ptcgp_auto_v2.infra.notifier import Notifier, get_notifier; n = get_notifier(); print('导入成功')"
```
  </action>
  <verify>
```bash
PYTHONPATH=src python -c "
from ptcgp_auto_v2.infra.notifier import Notifier, get_notifier

# 验证公共方法存在
n = get_notifier()
assert hasattr(n, 'notify')
assert hasattr(n, 'notify_rare_card')
assert hasattr(n, 'notify_task_status')
assert hasattr(n, 'notify_system_warning')
assert hasattr(n, 'send_webhook_test')
print('所有公共方法存在')
"
```
  </verify>
  <done>
- 导入无错误
- 所有公共方法可访问
- 功能验证通过
  </done>
</task>

</tasks>

<verification>
- [ ] 语法检查通过
- [ ] 行数减少约 20%（< 380 行）
- [ ] 公共方法签名不变
- [ ] 导入测试通过
- [ ] 功能完整性验证通过
</verification>

<success_criteria>
重构完成，notifier.py 从 441 行减少到约 350 行，减少静态方法 5 个，代码更简洁易读，功能完全不变。
</success_criteria>

<output>
After completion, create `.planning/quick/4-notifier-py/4-SUMMARY.md`
</output>

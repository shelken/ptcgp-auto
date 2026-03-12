## uiautomator2 输入法状态

- `uiautomator2 3.5.0` 的 `InputMethodMixIn.send_keys()` 成功后会主动广播 `ADB_KEYBOARD_HIDE`，但 `clear_text()` 只会广播 `ADB_KEYBOARD_CLEAR_TEXT`，不会隐藏输入法；筛选弹窗这类“清空后立刻返回继续点卡”的链路需要自己补一次隐藏。  
  来源: https://github.com/openatx/uiautomator2/blob/v3.5.0/uiautomator2/_input.py

- `3.5.0` 的发布说明明确提到修复了 `send_keys()` 结束后自动隐藏输入法的问题，说明输入法状态本身就是这个库近期修过的风险点。  
  来源: https://github.com/openatx/uiautomator2/releases/tag/3.5.0

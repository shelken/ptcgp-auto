---
name: add-task
description: 当我们需要添加某个任务时，我们需要获取页面ocr来完善页面规则的时候，当用户说了需要你帮忙调试页面的时候
---

## 原则

- 需要一边 发现/编写代码 一边获取用户的反馈，当有不明白的地方，需要跟用户沟通
- 以下所有python命令，均必须在uv下执行

## 场景

当用户没有说明需求，需让用户说明大概的需求。
当用户说明需求之后，应该检查adb地址，当用户没有说明adb地址时，应该询问adb地址
当我们在task编写过程中，需要编写pages规则时，我们需要发现哪些页面需要特定的文本或者模板来匹配时
当不知道某个页面如何抵达的时候，应该停下来询问用户
当用户提供需求文档，且文档中有ocr没有补充完善，需要询问是否补充完善，每次ocr之后寻找需要补充的部分，回填到文档的ocr内容
当遇到列表页面，当前页面没有目标时，往上滑动寻找更多
当完成了ocr补充的时候，如果用户需求中有不完善的地方，可以提出来让用户确认是否需要在需求文档中进行补充和修正

## 如何工作

- 使用已经编写的`debug_tool.py`来运行ocr和模板匹配进行发现元素和点击
- `python debug_tool.py -a [ADB_PORT] --ocr` 直接输出模拟器上的ocr内容
- `python debug_tool.py -a [ADB_PORT] --template [template_name] --scale 1.0` 直接输出模拟器上要寻找的模板位置以及所有文本ocr内容，template_name 是 当前项目根目录`templates/`下一级子文件。带上scale是为了防止进入自动缩放逻辑。
- 当需要点击某个页面去发现元素时，使用shell命令执行`adb -s 127.0.0.1:[ADB_PORT] shell ""`，必要时带上`su`
- 滑动使用`shell input swipe`
- 切换账号`python main_v2.py --switch-account [数据库accountid] -d [ADB_PORT]`
- 当需要返回时直接匹配模板`btn_back`和`btn_close`，`python debug_tool.py -a [ADB_PORT] --template btn_back --scale 1.0 && python debug_tool.py -a [ADB_PORT] --template btn_close --scale 1.0`，然后点击出现的返回或者关闭。

# -*- coding: utf-8 -*-
"""任务运行时状态容器。"""

from dataclasses import dataclass, field


@dataclass
class TaskState:
    """任务统一运行时状态。"""

    runtime: dict[str, object] = field(default_factory=dict)

    def reset(self):
        """重置全部运行时状态。"""
        self.runtime.clear()

    def get(self, key: str, default: object = None) -> object:
        """读取状态值。"""
        return self.runtime.get(key, default)

    def set(self, key: str, value: object):
        """设置状态值。"""
        self.runtime[key] = value

    def delete(self, key: str, default: object = None) -> object:
        """删除单个状态并返回旧值。"""
        return self.runtime.pop(key, default)

    def clear_prefix(self, prefix: str):
        """删除指定前缀的全部状态。"""
        keys = [key for key in self.runtime if key.startswith(prefix)]
        for key in keys:
            self.runtime.pop(key, None)

    def update(self, mapping: dict[str, object]):
        """批量更新状态。"""
        self.runtime.update(mapping)

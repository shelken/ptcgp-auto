"""
状态管理器 - 保存和加载自动化进度
"""

import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

import config


class StateManager:
    """管理自动化进度状态"""

    def __init__(self, state_file: str = "state.json"):
        self.state_file = Path(state_file)
        self.state: Dict = self._load_state()

    def _load_state(self) -> Dict:
        """加载状态文件"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    print(f"已加载状态: {self.state_file}")
                    return state
            except Exception as e:
                print(f"加载状态失败: {e}")

        # 初始化默认状态
        return self._create_default_state()

    def _create_default_state(self) -> Dict:
        """创建默认状态"""
        state = {
            "last_updated": datetime.now().isoformat(),
            "current_level": None,  # 当前正在处理的等级
            "current_series": "A",  # 当前系列 A/B
            "levels": {}
        }

        # 为每个等级创建状态
        for level in config.BATTLE_LEVELS:
            state["levels"][level] = {
                "complete": False,  # 是否显示 Complete
                "packs": {}  # 卡包完成状态
            }

        return state

    def save(self):
        """保存状态到文件"""
        self.state["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            if config.DEBUG:
                print(f"状态已保存: {self.state_file}")
        except Exception as e:
            print(f"保存状态失败: {e}")

    def reset(self):
        """重置状态"""
        self.state = self._create_default_state()
        self.save()
        print("状态已重置")

    # ===== 等级状态 =====

    def is_level_complete(self, level: str) -> bool:
        """检查等级是否完全完成（显示 Complete）"""
        if level in self.state["levels"]:
            return self.state["levels"][level].get("complete", False)
        return False

    def set_level_complete(self, level: str, complete: bool = True):
        """标记等级完成状态"""
        if level not in self.state["levels"]:
            self.state["levels"][level] = {"complete": False, "packs": {}}
        self.state["levels"][level]["complete"] = complete
        if complete:
            print(f"[状态] 等级 {level} 已标记为完成")
        self.save()

    def get_current_level(self) -> Optional[str]:
        """获取当前正在处理的等级"""
        return self.state.get("current_level")

    def set_current_level(self, level: str):
        """设置当前正在处理的等级"""
        self.state["current_level"] = level
        self.save()

    # ===== 卡包状态 =====

    def is_pack_complete(self, level: str, pack_name: str) -> bool:
        """检查指定等级的卡包是否完成"""
        if level in self.state["levels"]:
            packs = self.state["levels"][level].get("packs", {})
            return packs.get(pack_name, False)
        return False

    def set_pack_complete(self, level: str, pack_name: str, complete: bool = True):
        """标记卡包完成状态"""
        if level not in self.state["levels"]:
            self.state["levels"][level] = {"complete": False, "packs": {}}
        self.state["levels"][level]["packs"][pack_name] = complete
        if complete:
            print(f"[状态] {level} - {pack_name} 已标记为完成")
        self.save()

    def get_incomplete_packs(self, level: str) -> list:
        """获取指定等级未完成的卡包列表"""
        if level in self.state["levels"]:
            packs = self.state["levels"][level].get("packs", {})
            return [name for name, done in packs.items() if not done]
        return []

    # ===== 系列状态 =====

    def get_current_series(self) -> str:
        """获取当前系列"""
        return self.state.get("current_series", "A")

    def set_current_series(self, series: str):
        """设置当前系列"""
        self.state["current_series"] = series
        self.save()

    def switch_to_next_series(self) -> Optional[str]:
        """切换到下一个系列，返回新系列名，如果没有更多系列返回 None"""
        current = self.get_current_series()
        if current == "A":
            self.set_current_series("B")
            return "B"
        return None  # B 之后没有更多系列

    # ===== 工具方法 =====

    def get_next_incomplete_level(self) -> Optional[str]:
        """获取下一个未完成的等级"""
        for level in config.BATTLE_LEVELS:
            if not self.is_level_complete(level):
                return level
        return None

    def print_status(self):
        """打印当前状态摘要"""
        print("\n" + "=" * 40)
        print("当前进度:")
        print("=" * 40)
        for level in config.BATTLE_LEVELS:
            level_state = self.state["levels"].get(level, {})
            complete = "✓ Complete" if level_state.get("complete") else "进行中"
            packs = level_state.get("packs", {})
            done_count = sum(1 for v in packs.values() if v)
            total_count = len(packs)
            print(f"  {level}: {complete} ({done_count}/{total_count} 卡包)")
        print("=" * 40 + "\n")


# 全局实例（按文件名缓存）
_state_managers: Dict[str, StateManager] = {}


def get_state_manager(state_file: str = "state.json") -> StateManager:
    """获取状态管理器（按文件名缓存）"""
    global _state_managers
    if state_file not in _state_managers:
        _state_managers[state_file] = StateManager(state_file)
    return _state_managers[state_file]

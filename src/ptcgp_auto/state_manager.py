"""
状态管理器 - 保存和加载自动化进度
"""

import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from ptcgp_auto import config
from ptcgp_auto.logger import get_logger

logger = get_logger(__name__)


class StateManager:
    """管理自动化进度状态"""

    def __init__(self, state_file: str = "state.json"):
        self.state_file = Path(state_file)
        self.state: Dict = self._load_state()
        # 恢复状态后同步等级到日志上下文
        current_level = self.state.get("current_level")
        if current_level:
            from ptcgp_auto.logger import set_level

            set_level(current_level)

    def _load_state(self) -> Dict:
        """加载状态文件"""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)

                    # 检查语言是否一致，不一致则重置
                    saved_lang = state.get("language")
                    if saved_lang and saved_lang != config.LANGUAGE:
                        logger.info(f"语言已变更: {saved_lang} -> {config.LANGUAGE}")
                        logger.info("重置状态文件...")
                        self.state_file.unlink()
                        return self._create_default_state()

                    # 检查是否需要迁移（旧格式）
                    if self._needs_migration(state):
                        logger.info("检测到旧版本状态格式，重置状态文件...")
                        self.state_file.unlink()
                        return self._create_default_state()

                    logger.info(f"已加载状态: {self.state_file}")
                    return state
            except Exception as e:
                logger.error(f"加载状态失败: {e}")

        # 初始化默认状态
        return self._create_default_state()

    def _needs_migration(self, state: Dict) -> bool:
        """检测是否需要迁移
        - 旧格式1: 使用单一数字作为卡包 key
        - 旧格式2: 使用 {"name": ..., "done": bool} 作为值
        - 旧格式3: 使用 "数字_数字" 作为 key（无系列前缀）
        - 新格式: 使用 "系列_左分母_右分母" 作为 key（如 "a_20_81"），bool 作为值
        """
        levels = state.get("levels", {})
        for level_data in levels.values():
            packs = level_data.get("packs", {})
            for key, value in packs.items():
                # 如果 key 是纯数字（旧格式1），需要迁移
                if key.isdigit():
                    return True
                # 如果 value 是 dict（旧格式2），需要迁移
                if isinstance(value, dict):
                    return True
                # 检查 key 是否以任一已配置系列的小写前缀开头
                valid_prefixes = [f"{s.lower()}_" for s in config.SERIES]
                if not any(key.startswith(prefix) for prefix in valid_prefixes):
                    return True
        return False

    def _create_default_state(self) -> Dict:
        """创建默认状态"""
        state = {
            "language": config.LANGUAGE,  # 保存当前语言
            "last_updated": datetime.now().isoformat(),
            "current_level": None,  # 当前正在处理的等级
            "current_series": config.SERIES[0] if config.SERIES else "A",  # 当前系列
            "user": None,  # 用户信息：{username, friend_id, fetched_at}
            "user_db": None,  # 数据库用户信息缓存
            "levels": {},
        }

        # 为每个等级创建状态
        for level in config.BATTLE_LEVELS:
            state["levels"][level] = {
                "complete": False,  # 是否显示 Complete
                "packs": {},  # 卡包完成状态
            }

        return state

    def save(self):
        """保存状态到文件"""
        self.state["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            logger.debug(f"状态已保存: {self.state_file}")
        except Exception as e:
            logger.error(f"保存状态失败: {e}")

    def reset(self):
        """重置状态"""
        self.state = self._create_default_state()
        self.save()
        logger.info("状态已重置")

    # ===== 等级状态 =====

    def is_level_complete(self, level: str) -> bool:
        """检查等级是否完全完成（显示 Complete）"""
        if level in self.state["levels"]:
            return self.state["levels"][level].get("complete", False)
        return False

    def set_level_complete(
        self, level: str, complete: bool = True, notify: bool = False
    ):
        """标记等级完成状态

        Args:
            level: 等级名称
            complete: 是否完成
            notify: 是否发送通知（仅在实际完成对战时传 True，状态同步时不传）
        """
        if level not in self.state["levels"]:
            self.state["levels"][level] = {"complete": False, "packs": {}}

        # 检查是否是新完成的等级（之前未完成，现在完成）
        was_complete = self.state["levels"][level].get("complete", False)
        self.state["levels"][level]["complete"] = complete

        if complete:
            logger.info(f"[状态] 等级 {level} 已标记为完成")

            # 仅在实际完成时发送通知（非状态同步）
            if notify and not was_complete:
                from ptcgp_auto import config

                if config.NOTIFICATION_ENABLED:
                    from ptcgp_auto.notifier import notify_level_complete

                    username = None
                    if self.has_user_info():
                        user = self.get_user_info()
                        username = user.get("username")
                    notify_level_complete(
                        config.NOTIFICATION_WEBHOOK_KEY,
                        level,
                        config.NOTIFICATION_SOUND,
                        port=config.ADB_PORT,
                        username=username,
                    )
        self.save()

    def get_current_level(self) -> Optional[str]:
        """获取当前正在处理的等级"""
        return self.state.get("current_level")

    def set_current_level(self, level: str):
        """设置当前正在处理的等级"""
        self.state["current_level"] = level
        # 同步更新日志上下文中的等级
        from ptcgp_auto.logger import set_level

        set_level(level)
        self.save()

    # ===== 卡包状态 =====
    # packs 结构: {"系列_左分母_右分母": bool, ...}
    # 使用系列前缀+左右分母组合作为 key（如 "a_20_81"），因为不同系列可能有相同的分母组合
    # 系列 = a/b，左分母 = 总牌组数，右分母 = 总卡数

    def is_pack_complete(self, level: str, pack_id: str) -> bool:
        """检查指定等级的卡包是否完成（使用系列_左分母_右分母作为标识，如 'a_20_81'）"""
        if level in self.state["levels"]:
            packs = self.state["levels"][level].get("packs", {})
            return packs.get(pack_id, False)
        return False

    def set_pack_complete(self, level: str, pack_id: str, complete: bool = True):
        """标记卡包完成状态（使用系列_左分母_右分母作为标识，如 'a_20_81'）"""
        if level not in self.state["levels"]:
            self.state["levels"][level] = {"complete": False, "packs": {}}
        self.state["levels"][level]["packs"][pack_id] = complete
        if complete:
            logger.info(f"[状态] {level} - {pack_id} 已标记为完成")
        self.save()

    # ===== 系列状态 =====

    # ===== 用户信息 =====

    def has_user_info(self) -> bool:
        """检查是否已有用户信息"""
        user = self.state.get("user")
        return user is not None and user.get("friend_id") is not None

    def get_user_info(self) -> Optional[Dict]:
        """获取用户信息"""
        return self.state.get("user")

    def set_user_info(self, username: str, friend_id: str):
        """设置用户信息"""
        self.state["user"] = {
            "username": username,
            "friend_id": friend_id,
            "fetched_at": datetime.now().isoformat(),
        }
        logger.info(f"[状态] 已保存用户信息: {username} ({friend_id})")
        self.save()

    # ===== 工具方法 =====

    def needs_initialization(self) -> bool:
        """判断是否需要初始化状态（回单人对战主页读取）"""
        return self.state.get("current_level") is None

    def print_status(self):
        """打印当前状态摘要"""
        logger.info("\n" + "=" * 40)
        logger.info("当前进度:")
        logger.info("=" * 40)
        for level in config.BATTLE_LEVELS:
            level_state = self.state["levels"].get(level, {})
            complete = "✓ Complete" if level_state.get("complete") else "进行中"
            packs = level_state.get("packs", {})
            # 兼容新旧格式：新格式直接是 bool，旧格式是 dict
            done_count = sum(
                1
                for v in packs.values()
                if (v is True) or (isinstance(v, dict) and v.get("done"))
            )
            total_count = len(packs)
            logger.info(f"  {level}: {complete} ({done_count}/{total_count} 卡包)")
        logger.info("=" * 40 + "\n")


# 全局实例（按文件名缓存）
_state_managers: Dict[str, StateManager] = {}


def get_state_manager(state_file: str = "state.json") -> StateManager:
    """获取状态管理器（按文件名缓存）"""
    global _state_managers
    if state_file not in _state_managers:
        _state_managers[state_file] = StateManager(state_file)
    return _state_managers[state_file]

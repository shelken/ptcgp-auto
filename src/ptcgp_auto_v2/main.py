# -*- coding: utf-8 -*-
"""
PTCGP Auto v2 主入口

任务队列架构的自动化框架。
"""

import argparse
import logging
import sys
import threading
from pathlib import Path

import uvicorn
from ptcgp_auto_v2.config.settings import Settings, get_settings, set_settings
from ptcgp_auto_v2.config.pages.common import COMMON_PAGES
from ptcgp_auto_v2.core.scheduler import Scheduler, SchedulerConfig
from ptcgp_auto_v2.core.executor import ExecutorConfig
from ptcgp_auto_v2.core.task_base import TaskRegistry
from ptcgp_auto_v2.db.connection import get_database
from ptcgp_auto_v2.db.repositories import AccountRepository, TaskInstanceRepository
from ptcgp_auto_v2.infra.account_switcher import AccountSwitcher
from ptcgp_auto_v2.infra.account_syncer import AccountSyncer
from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.utils.device_discovery import discover_devices

# 导入任务模块以触发注册
import ptcgp_auto_v2.tasks

logger = logging.getLogger(__name__)


DEFAULT_WORKERS = 4  # 默认并发工作线程数


def normalize_device_addresses(devices: list[str]) -> list[str]:
    normalized = []
    for device in devices:
        if device.isdigit():
            normalized.append(f"127.0.0.1:{device}")
            continue
        if ":" in device:
            normalized.append(device)
            continue
        raise ValueError(f"设备地址格式不正确: {device}")
    return normalized


def parse_args(argv: list[str] | None = None):
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="PTCGP Auto v2 - 任务队列架构自动化框架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-d",
        "--devices",
        type=str,
        nargs="+",
        default=None,
        help="ADB 设备地址列表（未指定则自动发现 BlueStacks 设备）",
    )

    parser.add_argument(
        "--daemon",
        action="store_true",
        help="守护模式运行，持续调度任务",
    )

    parser.add_argument(
        "--single",
        action="store_true",
        help="单次运行模式，执行一轮任务后退出",
    )

    parser.add_argument(
        "--task",
        type=str,
        nargs="+",
        choices=TaskRegistry.all_types(),
        help="运行指定任务（可传多个，依次执行）",
    )

    parser.add_argument(
        "--account",
        type=int,
        help="指定账号 ID（与 --task 配合使用）",
    )

    parser.add_argument(
        "--switch-account",
        type=int,
        help="切换到指定账号",
    )

    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="列出所有已注册的任务类型",
    )

    parser.add_argument(
        "--list-accounts",
        action="store_true",
        help="列出所有账号",
    )

    parser.add_argument(
        "--sync-account",
        action="store_true",
        help="从设备同步当前登录的账号到数据库",
    )

    parser.add_argument(
        "--init-account",
        action="store_true",
        help="初始化设备账号环境（尝试备份当前账号 -> 重置游戏环境）",
    )

    parser.add_argument(
        "--reset-running",
        action="store_true",
        help="将所有运行中的任务重置为待执行",
    )

    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"最大并发执行器数（默认: {DEFAULT_WORKERS}）",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式",
    )

    parser.add_argument(
        "--disable-switch",
        action="store_true",
        help="使用设备当前账号，不切换",
    )

    parser.add_argument(
        "--list-plans",
        action="store_true",
        help="列出所有任务计划",
    )

    parser.add_argument(
        "--add-plan",
        type=str,
        help="为账号添加任务计划（需配合 --account 使用，可指定 ID 或名称）",
    )

    parser.add_argument(
        "--remove-plan",
        type=str,
        help="为账号移除任务计划（需配合 --account 使用，可指定 ID 或名称）",
    )

    # 自动创建账号相关参数
    parser.add_argument(
        "--auto-create-accounts",
        action="store_true",
        help="启用自动创建小号功能（默认关闭）",
    )

    parser.add_argument(
        "--max-accounts",
        type=int,
        default=100,
        help="自动创建账号的最大数量上限（默认：100）",
    )

    return parser.parse_args(argv)


def list_tasks():
    """列出所有已注册的任务类型"""
    print("\n已注册的任务类型:")
    print("-" * 40)
    for task_type in TaskRegistry.all_types():
        task_class = TaskRegistry.get(task_type)
        print(
            f"  - {task_type}: {task_class.__doc__.strip().split(chr(10))[0] if task_class.__doc__ else '无描述'}"
        )
    print()


def list_plans():
    """列出所有任务计划"""
    from ptcgp_auto_v2.db.repositories import TaskPlanRepository

    repo = TaskPlanRepository()
    plans = repo.get_all()

    print("\n任务计划列表:")
    print("-" * 60)
    print(f"{'ID':<5} {'名称':<20} {'描述':<30}")
    print("-" * 60)
    for plan in plans:
        desc = plan.description or "-"
        print(f"{plan.id:<5} {plan.name:<20} {desc:<30}")
        # 显示配置详情
        if plan.configuration and plan.configuration != "{}":
            print(f"      配置: {plan.configuration}")
        if plan.task_types:
            print(f"      任务: {plan.task_types}")
    print()


def manage_account_plan(account_id: int, plan_identifier: str, action: str):
    """
    管理账号的任务计划

    Args:
        account_id: 账号 ID
        plan_identifier: 计划 ID 或名称
        action: "add" 或 "remove"
    """
    from ptcgp_auto_v2.db.repositories import AccountRepository, TaskPlanRepository

    account_repo = AccountRepository()
    plan_repo = TaskPlanRepository()

    account = account_repo.get_by_id(account_id)
    if not account or account.id is None:
        print(f"错误: 账号 ID {account_id} 不存在")
        return

    # 解析 Plan
    plan = None
    if plan_identifier.isdigit():
        plan = plan_repo.get_by_id(int(plan_identifier))
    else:
        plan = plan_repo.get_by_name(plan_identifier)

    if not plan or plan.id is None:
        print(f"错误: 计划 '{plan_identifier}' 不存在")
        return

    if action == "add":
        if account_repo.add_secondary_plan(account.id, plan.id):
            print(f"成功: 已为账号 {account.nickname} 添加计划 '{plan.name}'")
        else:
            print(f"错误: 添加计划失败")
    elif action == "remove":
        if account_repo.remove_secondary_plan(account.id, plan.id):
            print(f"成功: 已从账号 {account.nickname} 移除计划 '{plan.name}'")
        else:
            print(f"错误: 移除计划失败")


def list_accounts():
    """列出所有账号"""
    repo = AccountRepository()
    accounts = repo.get_all()

    print("\n账号列表:")

    # 构建表格数据
    headers = ["ID", "游戏ID", "朋友ID", "昵称", "等级", "国家", "计划", "备注"]
    rows = []
    for account in accounts:
        # 获取主计划名称
        plan_name = "-"
        if account.task_plan_associations:
            active_assocs = [a for a in account.task_plan_associations if a.is_active]
            if active_assocs:
                # 按优先级降序排序
                active_assocs.sort(key=lambda x: (-x.priority, x.task_plan_id))
                primary_assoc = active_assocs[0]
                if primary_assoc.task_plan:
                    plan_name = primary_assoc.task_plan.name

        game_id = account.game_id[:16] if len(account.game_id) > 16 else account.game_id
        rows.append(
            [
                account.id,
                game_id,
                account.friend_id or "-",
                account.nickname or "-",
                account.level or "-",
                account.country or "-",
                plan_name,
                account.remark or "-",
            ]
        )

    # 计算每列最大宽度（考虑中文字符占2个宽度）
    def display_width(s):
        """计算字符串显示宽度（中文占2格）"""
        s = str(s)
        width = 0
        for c in s:
            width += 2 if ord(c) > 127 else 1
        return width

    def pad(s, width):
        """按显示宽度填充"""
        s = str(s)
        padding = width - display_width(s)
        return s + " " * padding

    # 计算列宽
    col_widths = [display_width(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], display_width(cell))

    # 打印表头
    header_line = "  ".join(pad(h, col_widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("-" * display_width(header_line))

    # 打印数据行
    for row in rows:
        print("  ".join(pad(str(cell), col_widths[i]) for i, cell in enumerate(row)))

    print(f"\n共 {len(accounts)} 个账号\n")


def reset_running_tasks():
    """将所有运行中的任务重置为待执行"""
    repo = TaskInstanceRepository()
    count = repo.reset_all_pending()
    print(f"已重置 {count} 个运行中的任务为待执行状态")


def sync_account(device_address: str):
    """
    从设备同步当前登录的账号到数据库

    Args:
        device_address: ADB 设备地址
    """
    from ptcgp_auto_v2.infra.adb import AdbController
    from ptcgp_auto_v2.infra.account_syncer import AccountSyncer

    print(f"\n正在连接设备: {device_address}")
    adb = AdbController(device_address)
    adb.connect()
    print("正在从设备提取账号信息...")
    syncer = AccountSyncer(adb)
    account = syncer.get_current_account()
    adb.disconnect()

    if account:
        print("\n账号同步成功!")
        print("-" * 40)
        print(f"  账号 ID:      {account.id}")
        print(f"  游戏 ID:      {account.game_id}")
        print(f"  朋友 ID:      {account.friend_id or '(待获取)'}")
        print(f"  Nintendo ID:  {account.nintendo_id or '(未绑定)'}")
        print(f"  昵称:         {account.nickname or '(未设置)'}")
        print(f"  国家/地区:    {account.country or '(未知)'}")
        print(f"  XML 已保存:   {'是' if account.xml_content else '否'}")
        print("-" * 40)
        return account.id
    else:
        print("\n警告: 无法获取账号信息")
        print("可能的原因:")
        print("  1. 设备未 Root")
        print("  2. 游戏未登录账号")
        print("  3. 游戏未安装或包名不匹配")
        return None


def run_init_account(device_address: str) -> bool:
    """
    初始化设备账号环境：
    1. 尝试同步(备份)当前账号到数据库
    2. 无论备份是否成功，都重置游戏环境

    Args:
        device_address: ADB 设备地址

    Returns:
        bool: 是否成功（指重置操作是否完成）
    """
    from ptcgp_auto_v2.infra.adb import AdbController
    from ptcgp_auto_v2.infra.account_switcher import AccountSwitcher
    from ptcgp_auto_v2.infra.account_syncer import AccountSyncer

    print(f"\n正在连接设备: {device_address}")
    adb = AdbController(device_address)

    try:
        adb.connect()

        # 1. 尝试同步/备份当前账号
        print("步骤 1/2: 正在尝试备份当前账号信息...")
        try:
            syncer = AccountSyncer(adb)
            account = syncer.get_current_account()
            if account:
                print(
                    f"账号已备份: {account.nickname or account.game_id} (ID: {account.id})"
                )
            else:
                print("未检测到有效账号或无法读取，跳过备份。")
        except Exception as e:
            logger.warning(f"备份账号时出错 (不影响重置): {e}")
            print("备份账号失败，继续执行重置...")

        # 2. 重置环境
        print("步骤 2/2: 正在重置游戏环境...")
        switcher = AccountSwitcher(adb)
        switcher.reset_game_environment()

        print("设备环境已初始化完成。")
        return True

    except Exception as e:
        logger.error(f"初始化设备环境失败: {e}")
        return False
    finally:
        adb.disconnect()


def run_switch_account(device: str, account_id: int) -> int:
    """切换到指定账号"""
    get_database()
    repo = AccountRepository()
    account = repo.get_by_id(account_id)
    if not account or not account.xml_content:
        logger.error(f"账号不存在或缺少 XML 内容: {account_id}")
        return 1

    adb = AdbController(device)
    try:
        adb.connect()
        syncer = AccountSyncer(adb)
        switcher = AccountSwitcher(adb)
        syncer.get_current_account()
        success = switcher.switch_to(account, restart_app=True)
        if not success:
            logger.error("账号切换失败")
            return 1
        logger.info(f"账号切换成功: {account_id}")
        return 0
    except Exception:
        logger.exception("切换账号失败")
        return 1
    finally:
        adb.disconnect()


def run_single_task(
    device: str, account_id: int, task_types: list[str], settings: Settings
):
    """运行指定任务（可传多个，依次执行）"""
    logger.info(
        f"运行任务: {', '.join(task_types)} (账号ID: {account_id}, 设备: {device})"
    )

    scheduler = Scheduler(
        device_addresses=[device],
        config=SchedulerConfig(
            max_workers=1,
            executor_config=ExecutorConfig(
                app_package=settings.app_package,
            ),
        ),
    )

    # 依次执行每个任务
    all_success = True
    for task_type in task_types:
        success = scheduler.run_single_task(device, account_id, task_type)
        if not success:
            logger.error(f"任务失败: {task_type}")
            all_success = False
            continue

    return 0 if all_success else 1


def run_web_server(host: str, port: int):
    """Run the web server"""
    try:
        from ptcgp_auto_v2.web.app import app

        # Disable Uvicorn's standard logging to prevent clutter, we have our own
        config = uvicorn.Config(
            app, host=host, port=port, log_level="warning", loop="asyncio"
        )
        server = uvicorn.Server(config)
        logger.info(f"Web server starting at http://{host}:{port}")
        server.run()
    except Exception as e:
        logger.error(f"Failed to start web server: {e}")


def run_daemon(settings: Settings, args: argparse.Namespace):
    """守护模式运行"""

    # Start web server in a background thread
    web_thread = threading.Thread(
        target=run_web_server, args=(settings.web_host, settings.web_port), daemon=True
    )
    web_thread.start()

    logger.info("启动守护模式...")

    # 配置自动创建账号参数
    auto_create = getattr(args, "auto_create_accounts", False)
    max_accounts = getattr(args, "max_accounts", 100)

    if auto_create:
        logger.info(f"已启用自动账号创建，最大数量: {max_accounts}")

    scheduler = Scheduler(
        device_addresses=settings.device_addresses,
        config=SchedulerConfig(
            poll_interval=settings.poll_interval,
            max_workers=settings.max_workers,
            task_generation_interval=settings.task_generation_interval,
            executor_config=ExecutorConfig(
                max_retries=settings.max_retries,
                retry_delay=settings.retry_delay,
                app_package=settings.app_package,
            ),
        ),
        auto_create_accounts=auto_create,
        max_accounts=max_accounts,
    )

    try:
        scheduler.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
        scheduler.stop(wait=True)

    return 0


def main():
    """主入口函数"""
    args = parse_args()

    device_addresses: list[str] | None = args.devices
    discovered_devices = False
    if not device_addresses:
        device_addresses = discover_devices()
        discovered_devices = True
        if not device_addresses:
            print("错误: 未发现 BlueStacks 设备，请通过 --devices 指定")
            return 1
    else:
        try:
            device_addresses = normalize_device_addresses(device_addresses)
        except ValueError as exc:
            print(f"错误: {exc}")
            return 1

    # 配置设置
    settings = Settings(
        device_addresses=device_addresses,
        max_workers=args.workers,
        debug=args.debug,
        log_level="DEBUG" if args.debug else "INFO",
    )
    set_settings(settings)
    settings.configure_logging()
    if discovered_devices and device_addresses:
        logger.info(f"自动发现设备: {', '.join(device_addresses)}")

    # 初始化数据库
    get_database()

    # 执行数据迁移
    from ptcgp_auto_v2.db.repositories import PackRecordRepository

    try:
        PackRecordRepository().migrate_legacy_data()
    except Exception as e:
        logger.warning(f"数据迁移失败: {e}")

    # 处理列表命令
    if args.list_tasks:
        list_tasks()
        return 0

    # 处理 Plan 管理命令
    if args.list_plans:
        list_plans()
        return 0

    if args.add_plan:
        if not args.account:
            print("错误: --add-plan 需要配合 --account 使用")
            return 1
        manage_account_plan(args.account, args.add_plan, "add")
        return 0

    if args.remove_plan:
        if not args.account:
            print("错误: --remove-plan 需要配合 --account 使用")
            return 1
        manage_account_plan(args.account, args.remove_plan, "remove")
        return 0

    if args.list_accounts:
        list_accounts()
        return 0

    if args.reset_running:
        reset_running_tasks()
        return 0

    if args.sync_account:
        # 对所有设备同步账号
        success = True
        for device in device_addresses:
            if not sync_account(device):
                success = False
        return 0 if success else 1

    if args.init_account:
        # 对所有设备执行初始化
        success = True
        for device in device_addresses:
            if not run_init_account(device):
                success = False
        return 0 if success else 1

    if args.switch_account is not None and args.task:
        logger.error("--switch-account 不能与 --task 同时使用")
        return 1

    if args.switch_account is not None and args.daemon:
        logger.error("--switch-account 不能与 --daemon 同时使用")
        return 1

    if args.switch_account is not None:
        if len(device_addresses) > 1:
            logger.warning("--switch-account 仅支持单设备，已使用第一个设备")
        device = device_addresses[0]
        return run_switch_account(device, args.switch_account)

    # 处理单任务模式
    if args.task:
        # Start web server even in single task mode if requested (optional, but good for monitoring)
        # For now, let's keep it simple and only run in daemon mode or if explicitly requested?
        # The user asked to integrate it so it runs in the background when the main app starts.
        # But typically "main app starts" implies daemon mode for long-running processes.
        # Let's add it to single task mode too if it doesn't exit immediately?
        # Actually single task mode exits after completion, so web server would die too.
        # So it makes most sense in daemon mode.

        # 原有错误处理保留
        if not args.account and not args.disable_switch:
            print("错误: --task 需要配合 --account 使用，或使用 --disable-switch")
            return 1
        device = device_addresses[0]
        # 新增：disable_switch 时从设备获取账号
        account_id = args.account
        if args.disable_switch and account_id is None:
            account_id = sync_account(device)
            if account_id is None:
                logger.error("无法获取设备当前账号")
                return 1

        return run_single_task(device, account_id, args.task, settings)

    # 守护模式
    if args.daemon:
        return run_daemon(settings, args)

    # 默认：显示帮助
    print("PTCGP Auto v2 - 任务队列架构自动化框架")
    print()
    print("使用方式:")
    print("  python main_v2.py --daemon                    # 守护模式")
    print("  python main_v2.py --list-tasks                # 列出任务")
    print("  python main_v2.py --list-accounts             # 列出账号")
    print("  python main_v2.py --switch-account 4 -d 5715  # 切换账号")
    print("  python main_v2.py --sync-account              # 同步当前设备账号")
    print("  python main_v2.py --sync-account -d 127.0.0.1:5556  # 指定设备同步")
    print("  python main_v2.py --task open_pack --account 1              # 单任务")
    print("  python main_v2.py --task claim_rewards open_pack --account 1  # 多任务")
    print()
    print("更多选项请使用 --help 查看")

    return 0


if __name__ == "__main__":
    sys.exit(main())

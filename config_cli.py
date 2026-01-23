#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开包配置 CLI

使用方向键选择账号并配置每日开包目标。
"""

import argparse
import sys
from pathlib import Path
import json

import questionary
from questionary import Choice

# 将 src 加入路径
ROOT_DIR = Path(__file__).parent
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from ptcgp_auto_v2.db.connection import get_database
from ptcgp_auto_v2.db.models import AccountPackConfig
from ptcgp_auto_v2.db.repositories import (
    AccountRepository,
    AccountPackConfigRepository,
    CardRepository,
)

# 特殊值：返回上一级
BACK = "__BACK__"


def list_accounts():
    repo = AccountRepository()
    accounts = repo.get_all()
    if not accounts:
        print("暂无账号")
        return []
    print(f"共 {len(accounts)} 个账号：")
    print("ID\tGameID\tNickname")
    for acc in accounts:
        nickname = acc.nickname or "-"
        print(f"{acc.id}\t{acc.game_id}\t{nickname}")
    return accounts


def update_nickname(account_id: int, nickname: str) -> int:
    repo = AccountRepository()
    account = repo.get_by_id(account_id)
    if not account:
        print(f"账号不存在: {account_id}")
        return 1
    account.nickname = nickname
    repo.update(account)
    print(f"已更新账号 {account_id} 的昵称为: {nickname}")
    return 0


def list_pack_configs(account_id: int):
    cfg_repo = AccountPackConfigRepository()
    configs = cfg_repo.get_by_account(account_id)
    if not configs:
        print("未找到开包配置")
        return []
    print(f"账号 {account_id} 的开包配置：")
    print("ID\tType\tPackCode\tBooster")
    for cfg in configs:
        print(f"{cfg.id}\t{cfg.type}\t{cfg.pack_code}\t{cfg.booster_name}")
    return configs


def set_pack_config(account_id: int, pack_code: str, booster_name: str, cfg_type: str):
    acc_repo = AccountRepository()
    account = acc_repo.get_by_id(account_id)
    if not account:
        print(f"账号不存在: {account_id}")
        return 1

    cfg_repo = AccountPackConfigRepository()
    config = AccountPackConfig(
        account_id=account_id,
        type=cfg_type,
        pack_code=pack_code,
        booster_name=booster_name,
    )
    cfg_repo.upsert(config)
    print(
        f"已更新账号 {account_id} 的开包配置: type={cfg_type}, pack={pack_code}/{booster_name}"
    )
    return 0


def delete_pack_config(config_id: int):
    cfg_repo = AccountPackConfigRepository()
    cfg_repo.delete(config_id)
    print(f"已删除开包配置 {config_id}")


def interactive():
    repo = AccountRepository()
    accounts = repo.get_all()
    if not accounts:
        print("暂无账号")
        return 0

    while True:
        # 1. 选择账号（方向键）
        account_choices = [
            Choice(
                title=f"[{acc.id}] {acc.game_id} - {acc.nickname or '(无昵称)'}",
                value=acc,
            )
            for acc in accounts
        ]
        account_choices.append(Choice(title="← 退出", value=None))

        selected_account = questionary.select(
            "选择账号:",
            choices=account_choices,
        ).ask()

        if selected_account is None:
            print("已退出")
            return 0

        # 进入账号操作菜单
        result = _account_menu(selected_account)
        if result == BACK:
            continue  # 返回账号选择
        return result


def _account_menu(account) -> int | str:
    """账号操作菜单，返回 BACK 表示返回上一级"""
    while True:
        # 显示当前配置
        list_pack_configs(account.id)

        # 选择操作（方向键）
        operation = questionary.select(
            "选择操作:",
            choices=[
                Choice(title="设置/更新开包配置", value="set"),
                Choice(title="删除开包配置", value="delete"),
                Choice(title="修改昵称", value="nickname"),
                Choice(title="← 返回账号列表", value=BACK),
                Choice(title="← 退出", value="exit"),
            ],
        ).ask()

        if operation == "exit" or operation is None:
            print("已退出")
            return 0

        if operation == BACK:
            return BACK

        if operation == "set":
            result = _interactive_set_config(account.id)
            if result == BACK:
                continue  # 返回操作菜单
            return result

        if operation == "delete":
            result = _interactive_delete_config(account.id)
            if result == BACK:
                continue
            # 删除后继续显示菜单
            continue

        if operation == "nickname":
            new_nick = questionary.text(
                "输入新的昵称:",
                default=account.nickname or "",
            ).ask()
            if new_nick is None:
                continue  # 取消，返回操作菜单
            if new_nick:
                update_nickname(account.id, new_nick)
                account.nickname = new_nick  # 更新内存中的值
            else:
                print("昵称不能为空")
            continue  # 继续显示菜单


def _interactive_set_config(account_id: int) -> int | str:
    """交互式设置开包配置，返回 BACK 表示返回上一级"""
    repo = CardRepository()
    sets = repo.get_all_sets()
    if not sets:
        print("数据库中没有卡包数据，请先运行 sync_metadata.py")
        return 1

    # 选择扩充包（方向键）
    pack_choices = [
        Choice(
            title=f"{s.code}: {s.name}",
            value=s.code,
        )
        for s in sets
    ]
    pack_choices.insert(0, Choice(title="← 返回", value=BACK))

    pack_code = questionary.select(
        "选择扩充包:",
        choices=pack_choices,
    ).ask()

    if pack_code is None or pack_code == BACK:
        return BACK

    # 选择子包（方向键）
    # 从数据库获取子包列表
    pack_data = repo.get_packs_by_set(pack_code)
    boosters = pack_data.get(pack_code, {}).get("boosters", [])

    if not boosters:
        print(f"扩充包 {pack_code} 没有子包数据")
        return 1

    booster_choices = [Choice(title=b, value=b) for b in boosters]
    booster_choices.insert(0, Choice(title="← 返回", value=BACK))

    booster_name = questionary.select(
        "选择子包:",
        choices=booster_choices,
    ).ask()

    if booster_name is None or booster_name == BACK:
        return BACK

    # 选择配置类型（方向键）
    cfg_type = questionary.select(
        "配置类型:",
        choices=[
            Choice(title="daily (每日)", value="daily"),
            Choice(title="once (一次性)", value="once"),
            Choice(title="← 返回", value=BACK),
        ],
        default="daily",
    ).ask()

    if cfg_type is None or cfg_type == BACK:
        return BACK

    return set_pack_config(account_id, pack_code, booster_name, cfg_type)


def _interactive_delete_config(account_id: int) -> int | str:
    """交互式删除开包配置，返回 BACK 表示返回上一级"""
    cfg_repo = AccountPackConfigRepository()
    configs = cfg_repo.get_by_account(account_id)

    if not configs:
        print("该账号没有开包配置")
        return BACK

    # 选择要删除的配置（方向键）
    config_choices = [
        Choice(
            title=f"[{cfg.id}] {cfg.type}: {cfg.pack_code}/{cfg.booster_name}",
            value=cfg.id,
        )
        for cfg in configs
    ]
    config_choices.insert(0, Choice(title="← 返回", value=BACK))

    config_id = questionary.select(
        "选择要删除的配置:",
        choices=config_choices,
    ).ask()

    if config_id is None or config_id == BACK:
        return BACK

    # 确认删除
    confirm = questionary.confirm(
        f"确认删除配置 {config_id}?",
        default=False,
    ).ask()

    if confirm:
        delete_pack_config(config_id)

    return BACK  # 删除后返回上一级


def parse_args():
    parser = argparse.ArgumentParser(description="开包配置 CLI")
    sub = parser.add_subparsers(dest="command", required=False)

    sub.add_parser("list-accounts", help="列出账号")

    p_list = sub.add_parser("list-configs", help="查看账号的开包配置")
    p_list.add_argument("account_id", type=int, help="账号 ID")

    p_set = sub.add_parser("set-config", help="设置/更新开包配置")
    p_set.add_argument("account_id", type=int, help="账号 ID")
    p_set.add_argument("pack_code", type=str, help="扩充包代码，如 A4a")
    p_set.add_argument("booster_name", type=str, help="卡包名称")
    p_set.add_argument(
        "--type", default="daily", choices=["daily", "once"], help="配置类型"
    )

    p_del = sub.add_parser("delete-config", help="删除开包配置")
    p_del.add_argument("config_id", type=int, help="配置 ID")

    sub.add_parser("interactive", help="交互模式：选择账号并设置/删除配置")

    return parser.parse_args()


def main():
    get_database()  # 确保数据库初始化
    args = parse_args()

    if not args.command:
        return interactive()

    if args.command == "list-accounts":
        list_accounts()
        return 0
    elif args.command == "list-configs":
        list_pack_configs(args.account_id)
        return 0
    elif args.command == "set-config":
        return set_pack_config(
            args.account_id, args.pack_code, args.booster_name, args.type
        )
    elif args.command == "delete-config":
        delete_pack_config(args.config_id)
        return 0
    elif args.command == "interactive":
        return interactive()

    return 0


if __name__ == "__main__":
    sys.exit(main())

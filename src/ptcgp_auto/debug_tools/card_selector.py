# -*- coding: utf-8 -*-
"""
交互式卡牌选择器
"""
from typing import List, Optional

import questionary
from sqlmodel import Session, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import Card, CardPack
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.utils.image_manager import ImageResourceManager


class CardSelector:
    def __init__(self):
        self.repo = CardRepository()

    def select_card_interactively(
        self, series_code: str, pack_name: Optional[str] = None, rarity: Optional[str] = None
    ) -> List[str]:
        """
        交互式选择卡牌，返回 identifiers (Series/Pack/Filename)
        """
        try:
            with Session(get_engine()) as session:
                # 1. 构建查询
                query = select(Card).where(Card.set_code == series_code)

                if rarity:
                    query = query.where(Card.rarity == rarity)

                if pack_name:
                    query = query.join(CardPack, Card.id == CardPack.card_id).where(
                        CardPack.pack_name == pack_name
                    )

                query = query.order_by(Card.number)
                cards = list(session.exec(query).all())

                if not cards:
                    print(f"没有找到符合条件的卡牌: Series={series_code}, Pack={pack_name}, Rarity={rarity}")
                    return []

                # 2. 构造选项
                choices = []
                for card in cards:
                    # 格式: [001] (RR) Exeggcute
                    label = f"[{card.number:03d}] ({card.rarity}) {card.name}"
                    choices.append(questionary.Choice(title=label, value=card))

                # 3. 使用 questionary 进行选择
                selected_cards = questionary.checkbox(
                    f"Found {len(cards)} cards. Select cards to debug:",
                    choices=choices,
                    validate=lambda x: True if x else "Must select at least one card"
                ).ask()

                if not selected_cards:
                    return []

                # 4. 构造返回值
                results = []
                for card in selected_cards:
                    # 确定 pack_name 用于文件路径
                    target_pack = pack_name
                    if not target_pack:
                        if card.packs:
                            target_pack = card.packs[0].pack_name
                        else:
                            print(f"Warning: Card {card.name} has no associated pack, skipping.")
                            continue

                    # 构造文件名
                    # 使用 ImageResourceManager 的统一命名规则
                    # get_card_filename 返回带 .png 后缀的文件名
                    full_filename = ImageResourceManager.get_card_filename(card)

                    # 这里的 identifier 需要不带后缀的名称还是带后缀的？
                    # non_interactive.py 里 parts[-1] 会被当做 card_name
                    # 如果不带 .png，non_interactive 会加上 .png
                    # 之前的代码是返回带 .png 的 identifier，然后 non_interactive 也能处理
                    # 为了清晰起见，这里去除 .png 后缀，让 non_interactive 决定
                    # 但是 ImageResourceManager.get_card_filename 强制返回 .png
                    # 所以我们需要 strip
                    card_filename = full_filename.removesuffix(".png")

                    identifier = f"{series_code}/{target_pack}/{card_filename}"
                    results.append(identifier)

                print(f"Selected {len(results)} cards.")
                return results

        except ImportError:
            print("ERROR: 无法导入数据库模块，请确保环境配置正确")
            return []
        except Exception as e:
            print(f"ERROR: 选择过程出错: {e}")
            import traceback
            traceback.print_exc()
            return []

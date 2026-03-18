# -*- coding: utf-8 -*-
"""
Repository 基类

统一绑定外部传入的 Session。

Repository 本身不拥有事务边界，也不负责创建和关闭 Session。
"""

from dataclasses import fields, is_dataclass
from typing import TypeVar

from sqlmodel import Session

T = TypeVar("T")


class BaseRepository:
    """Repository 基类。"""

    def __init__(self, session: Session):
        """绑定外部 Session。"""
        self.session = session

    def _finish_write(self, *instances: object):
        """统一完成写入，仅 flush 当前事务。"""
        self.session.flush()

        for instance in instances:
            if instance is not None:
                self.session.refresh(instance)

    def _to_data(self, data_type: type[T], model: object) -> T:
        """按 dataclass 字段名把 ORM 模型投影为纯数据。"""
        if not is_dataclass(data_type):
            raise TypeError(f"{data_type} 不是 dataclass")
        return data_type(
            **{
                item.name: getattr(model, item.name)
                for item in fields(data_type)
            }
        )

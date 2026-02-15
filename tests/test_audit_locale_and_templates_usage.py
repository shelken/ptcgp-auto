# -*- coding: utf-8 -*-
"""审计脚本测试。"""

import importlib.util
import sys
from pathlib import Path


def _load_audit_module():
    """按文件路径加载审计脚本模块。"""
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "audit_locale_and_templates_usage.py"
    )
    spec = importlib.util.spec_from_file_location("audit_locale", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_locale_keys(tmp_path: Path):
    """应能从 locale 文件提取 key。"""
    module = _load_audit_module()
    locale_file = tmp_path / "zh_Hant.py"
    locale_file.write_text(
        "TEXT_PATTERNS = {\n    'foo': ['a'],\n    'bar': ['b'],\n}\n",
        encoding="utf-8",
    )

    keys = module.extract_locale_keys(locale_file)
    assert keys == ["foo", "bar"]


def test_collect_locale_key_occurrences_scan_anywhere(tmp_path: Path):
    """应按源码中任意出现位置统计 key。"""
    module = _load_audit_module()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    file_a = src_dir / "a.py"
    file_a.write_text("x = 'error_code_103_011_05400'\n", encoding="utf-8")
    file_b = src_dir / "b.py"
    file_b.write_text("y = get_text_patterns('foo')\n", encoding="utf-8")

    result = module.collect_locale_key_occurrences(
        keys=["error_code_103_011_05400", "foo", "not_used"],
        source_root=src_dir,
    )

    assert result["error_code_103_011_05400"]
    assert result["foo"]
    assert result["not_used"] == []


def test_extract_template_names_with_first_level_subdirs(tmp_path: Path):
    """应收集 templates 根目录与一级子目录模板名。"""
    module = _load_audit_module()
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "icon_home.png").write_bytes(b"x")
    (templates / "btn_close.jpg").write_bytes(b"x")
    sub = templates / "packs_auto"
    sub.mkdir()
    (sub / "foo.webp").write_bytes(b"x")
    deep = sub / "deep"
    deep.mkdir()
    (deep / "ignored.png").write_bytes(b"x")

    names = module.extract_template_names(templates)

    assert "icon_home" in names
    assert "btn_close" in names
    assert "packs_auto/foo" in names
    assert "packs_auto/deep/ignored" not in names


def test_clean_and_sort_locale_file(tmp_path: Path):
    """clean+sort 应删除无用 key，并按字母序输出且无注释行。"""
    module = _load_audit_module()
    locale_file = tmp_path / "zh_Hant.py"
    locale_file.write_text(
        "TEXT_PATTERNS = {\n"
        "    # 注释\n"
        "    'b_key': ['b'],\n"
        "    'a_key': ['a'],\n"
        "    'dead_key': ['x'],\n"
        "}\n",
        encoding="utf-8",
    )

    module.clean_and_sort_locale_file(
        locale_file=locale_file,
        keep_keys={"a_key", "b_key"},
        sort_keys=True,
    )

    content = locale_file.read_text(encoding="utf-8")
    assert "dead_key" not in content
    assert "# 注释" not in content
    assert content.index('"a_key"') < content.index('"b_key"')


def test_align_locale_file_to_base(tmp_path: Path):
    """对齐应补齐缺失 key、删除多余 key。"""
    module = _load_audit_module()
    locale_file = tmp_path / "en_US.py"
    locale_file.write_text(
        "TEXT_PATTERNS = {\n    'a_key': ['A'],\n    'extra_key': ['X'],\n}\n",
        encoding="utf-8",
    )
    base_dict = {"a_key": ["a"], "b_key": ["b"]}

    module.align_locale_file_to_base(
        locale_file=locale_file,
        base_dict=base_dict,
        sort_keys=True,
    )

    content = locale_file.read_text(encoding="utf-8")
    assert "extra_key" not in content
    assert '"a_key"' in content
    assert '"b_key"' in content


def test_remove_keys_preserve_layout_keep_comments(tmp_path: Path):
    """clean（不 sort）应尽量保留注释与原有布局。"""
    module = _load_audit_module()
    locale_file = tmp_path / "zh_Hant.py"
    locale_file.write_text(
        '# -*- coding: utf-8 -*-\nTEXT_PATTERNS = {\n    # 区段\n    "keep": ["v"],\n    "drop": ["x"],\n}\n',
        encoding="utf-8",
    )

    module._remove_keys_preserve_layout(locale_file, {"drop"})
    content = locale_file.read_text(encoding="utf-8")

    assert "# 区段" in content
    assert '"keep"' in content
    assert '"drop"' not in content


def test_collect_locale_key_occurrences_support_dynamic_fstring(tmp_path: Path):
    """应识别 get_text_patterns 动态 f-string key。"""
    module = _load_audit_module()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    file_a = src_dir / "a.py"
    file_a.write_text(
        'def x(tab):\n    return get_text_patterns(f"rewards_tab_{tab}")\n',
        encoding="utf-8",
    )

    result = module.collect_locale_key_occurrences(
        keys=["rewards_tab_daily", "rewards_tab_premium", "not_used"],
        source_root=src_dir,
        include_dynamic=True,
    )

    assert result["rewards_tab_daily"]
    assert result["rewards_tab_premium"]
    assert result["not_used"] == []


def test_load_locale_support_from_constants(tmp_path: Path):
    """应从 constants.py 提取支持语言与映射。"""
    module = _load_audit_module()
    constants_file = tmp_path / "constants.py"
    constants_file.write_text(
        "SUPPORTED_LOCALES = ['zh_Hant', 'en_US']\n"
        "LOCALE_TO_OCR_LANGUAGE = {'zh_Hant': 'zh-Hant', 'en_US': 'en-US'}\n",
        encoding="utf-8",
    )

    locales, mapping = module.load_locale_support_from_constants(constants_file)
    assert locales == ["zh_Hant", "en_US"]
    assert mapping["zh_Hant"] == "zh-Hant"
    assert mapping["en_US"] == "en-US"


def test_load_locale_support_from_constants_fallback_mapping_keys(tmp_path: Path):
    """SUPPORTED_LOCALES 非字面量时应回退使用映射 key。"""
    module = _load_audit_module()
    constants_file = tmp_path / "constants.py"
    constants_file.write_text(
        "LOCALE_TO_OCR_LANGUAGE = {'zh_Hant': 'zh-Hant', 'en_US': 'en-US'}\n"
        "SUPPORTED_LOCALES = list(LOCALE_TO_OCR_LANGUAGE.keys())\n",
        encoding="utf-8",
    )

    locales, mapping = module.load_locale_support_from_constants(constants_file)
    assert locales == ["zh_Hant", "en_US"]
    assert mapping["zh_Hant"] == "zh-Hant"


def test_ensure_supported_locale_files(tmp_path: Path):
    """应按支持语言自动生成缺失 locale 文件。"""
    module = _load_audit_module()
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    (locales_dir / "zh_Hant.py").write_text(
        'TEXT_PATTERNS = {"k": ["v"]}\n',
        encoding="utf-8",
    )

    created = module.ensure_supported_locale_files(
        locales_dir=locales_dir,
        supported_locales=["zh_Hant", "en_US"],
        base_dict={"k": ["v"]},
        sort_keys=False,
    )

    assert (locales_dir / "en_US.py").exists()
    assert created and created[0].name == "en_US.py"

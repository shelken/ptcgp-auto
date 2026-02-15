# -*- coding: utf-8 -*-
"""使用 ripgrep 审计 locale key 与模板使用情况。"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TEMPLATE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class Hit:
    """检索命中。"""

    file: str
    line: int
    content: str


def extract_locale_keys(locale_file: Path) -> list[str]:
    """从 locale 文件提取 TEXT_PATTERNS 全量 key。"""
    source = locale_file.read_text(encoding="utf-8")
    module = ast.parse(source)

    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "TEXT_PATTERNS"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Dict):
            continue

        keys: list[str] = []
        for key in node.value.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.append(key.value)
        return keys

    raise ValueError(f"未在 {locale_file} 中找到 TEXT_PATTERNS")


def load_text_patterns_dict(locale_file: Path) -> dict[str, Any]:
    """加载 locale 文件中的 TEXT_PATTERNS 为可编辑字典。"""
    source = locale_file.read_text(encoding="utf-8")
    module = ast.parse(source)
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "TEXT_PATTERNS"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        return ast.literal_eval(node.value)
    raise ValueError(f"未在 {locale_file} 中找到 TEXT_PATTERNS")


def _render_value(value: Any, indent: int = 4) -> str:
    """把 dict/list/str 基础结构渲染为 Python 字面量。"""
    pad = " " * indent
    next_pad = " " * (indent + 4)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        if not value:
            return "[]"
        if all(isinstance(item, str) for item in value):
            inline_items = ", ".join(
                json.dumps(item, ensure_ascii=False) for item in value
            )
            inline = f"[{inline_items}]"
            if len(inline) <= 88:
                return inline
        lines = ["["]
        for item in value:
            lines.append(f"{next_pad}{_render_value(item, indent + 4)},")
        lines.append(f"{pad}]")
        return "\n".join(lines)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for key, item in value.items():
            lines.append(
                f"{next_pad}{json.dumps(str(key), ensure_ascii=False)}: {_render_value(item, indent + 4)},"
            )
        lines.append(f"{pad}}}")
        return "\n".join(lines)
    return repr(value)


def write_text_patterns_dict(locale_file: Path, data: dict[str, Any], sort_keys: bool):
    """重写 locale 文件，去掉注释行并按需要排序 key。"""
    items = (
        sorted(data.items(), key=lambda item: item[0])
        if sort_keys
        else list(data.items())
    )
    lines = [
        "# -*- coding: utf-8 -*-",
        '"""繁体中文文本配置（自动生成）"""',
        "",
        "TEXT_PATTERNS = {",
    ]
    for key, value in items:
        rendered = _render_value(value, indent=4)
        if "\n" not in rendered:
            lines.append(f"    {json.dumps(key, ensure_ascii=False)}: {rendered},")
            continue
        value_lines = rendered.splitlines()
        lines.append(f"    {json.dumps(key, ensure_ascii=False)}: {value_lines[0]}")
        for value_line in value_lines[1:]:
            lines.append(value_line)
        lines[-1] = f"{lines[-1]},"
    lines.append("}")
    lines.append("")
    locale_file.write_text("\n".join(lines), encoding="utf-8")


def clean_and_sort_locale_file(locale_file: Path, keep_keys: set[str], sort_keys: bool):
    """清理 locale 无用 key，并按需排序重写文件。"""
    data = load_text_patterns_dict(locale_file)
    cleaned = {k: v for k, v in data.items() if k in keep_keys}
    write_text_patterns_dict(locale_file, cleaned, sort_keys=sort_keys)


def _find_text_patterns_block(lines: list[str]) -> tuple[int, int]:
    """定位 TEXT_PATTERNS 字典块起止行（含首尾）。"""
    start = -1
    for idx, line in enumerate(lines):
        if "TEXT_PATTERNS" in line and "{" in line:
            start = idx
            break
    if start == -1:
        raise ValueError("未找到 TEXT_PATTERNS 起始位置")

    depth = 0
    started = False
    for idx in range(start, len(lines)):
        raw = lines[idx]
        for ch in raw:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
                if started and depth == 0:
                    return start, idx
    raise ValueError("未找到 TEXT_PATTERNS 结束位置")


def _entry_key_from_line(line: str) -> str | None:
    """从顶层 key 行提取 key。"""
    match = re.match(r"^\s*([\"'])(.+?)\1\s*:", line)
    if not match:
        return None
    return match.group(2)


def _remove_keys_preserve_layout(locale_file: Path, remove_keys: set[str]):
    """仅删除指定 key，尽量保留原文件布局（用于 --clean 且不 --sort）。"""
    lines = locale_file.read_text(encoding="utf-8").splitlines(keepends=True)
    start, end = _find_text_patterns_block(lines)

    body = lines[start + 1 : end]
    output_body: list[str] = []

    current_key: str | None = None
    current_block: list[str] = []
    current_depth = 1

    def flush_block():
        nonlocal current_key, current_block
        if current_key is None:
            output_body.extend(current_block)
        elif current_key not in remove_keys:
            output_body.extend(current_block)
        current_key = None
        current_block = []

    for line in body:
        new_key = _entry_key_from_line(line) if current_depth == 1 else None
        if new_key is not None:
            flush_block()
            current_key = new_key
        current_block.append(line)

        # 仅用括号平衡控制顶层深度，配置文本中不含括号字面量，足够稳定。
        current_depth += line.count("{") + line.count("[")
        current_depth -= line.count("}") + line.count("]")

    flush_block()

    new_lines = lines[: start + 1] + output_body + lines[end:]
    locale_file.write_text("".join(new_lines), encoding="utf-8")


def align_locale_file_to_base(
    locale_file: Path,
    base_dict: dict[str, Any],
    sort_keys: bool,
):
    """按基准 locale 对齐其他 locale 的 key 集。"""
    current = load_text_patterns_dict(locale_file)
    aligned: dict[str, Any] = {}
    for key, base_value in base_dict.items():
        aligned[key] = current.get(key, base_value)
    write_text_patterns_dict(locale_file, aligned, sort_keys=sort_keys)


def list_locale_files(locales_dir: Path) -> list[Path]:
    """列出 locales 目录下所有 locale 文件（排除 __init__.py）。"""
    files = []
    for file in locales_dir.glob("*.py"):
        if file.name == "__init__.py":
            continue
        files.append(file)
    return sorted(files)


def load_locale_support_from_constants(
    constants_file: Path,
) -> tuple[list[str], dict[str, str]]:
    """从 constants.py 读取支持语言与 OCR 映射。"""
    source = constants_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    supported: list[str] = []
    mapping: dict[str, str] = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "SUPPORTED_LOCALES":
                try:
                    value = ast.literal_eval(node.value)
                except Exception:
                    value = None
                if isinstance(value, list):
                    supported = [str(item) for item in value]
            if target.id == "LOCALE_TO_OCR_LANGUAGE":
                value = ast.literal_eval(node.value)
                if isinstance(value, dict):
                    mapping = {str(k): str(v) for k, v in value.items()}

    # 当 SUPPORTED_LOCALES 不是字面量（例如 list(LOCALE_TO_OCR_LANGUAGE.keys())）时，回退为映射键
    if not supported and mapping:
        supported = list(mapping.keys())

    return supported, mapping


def ensure_supported_locale_files(
    locales_dir: Path,
    supported_locales: list[str],
    base_dict: dict[str, Any],
    sort_keys: bool,
) -> list[Path]:
    """确保支持语言对应的 locale 文件存在，不存在则自动生成。"""
    created: list[Path] = []
    for locale_name in supported_locales:
        locale_file = locales_dir / f"{locale_name}.py"
        if locale_file.exists():
            continue
        write_text_patterns_dict(locale_file, dict(base_dict), sort_keys=sort_keys)
        created.append(locale_file)
    return created


def extract_template_names(templates_dir: Path) -> list[str]:
    """提取 templates 根目录与一级子目录模板名（无扩展名）。"""
    names: set[str] = set()
    if not templates_dir.exists():
        return []

    for item in templates_dir.iterdir():
        if item.is_file() and item.suffix.lower() in TEMPLATE_EXTENSIONS:
            names.add(item.stem)
            continue

        if not item.is_dir():
            continue
        for sub_item in item.iterdir():
            if sub_item.is_file() and sub_item.suffix.lower() in TEMPLATE_EXTENSIONS:
                names.add(f"{item.name}/{sub_item.stem}")

    return sorted(names)


def _parse_rg_line(line: str) -> Hit | None:
    """解析 rg 的 `path:line:content` 单行输出。"""
    parts = line.split(":", 2)
    if len(parts) != 3:
        return None
    path, line_no, content = parts
    if not line_no.isdecimal():
        return None
    return Hit(file=path, line=int(line_no), content=content.strip())


def _run_rg_literal(token: str, search_root: Path, globs: list[str]) -> list[Hit]:
    """调用 rg 做固定字符串检索，返回命中列表。"""
    command = [
        "rg",
        "--no-heading",
        "--line-number",
        "--color",
        "never",
        "-F",
        token,
    ]
    for glob in globs:
        command.extend(["-g", glob])
    command.append(str(search_root))

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"rg 执行失败，token={token}, code={result.returncode}, stderr={result.stderr.strip()}"
        )

    hits: list[Hit] = []
    for line in result.stdout.splitlines():
        parsed = _parse_rg_line(line)
        if parsed is not None:
            hits.append(parsed)
    return hits


def _run_rg_quoted_token(token: str, search_root: Path, globs: list[str]) -> list[Hit]:
    """仅匹配被单/双引号包裹的 token。"""
    command = [
        "rg",
        "--no-heading",
        "--line-number",
        "--color",
        "never",
        "-e",
        f'"{token}"',
        "-e",
        f"'{token}'",
    ]
    for glob in globs:
        command.extend(["-g", glob])
    command.append(str(search_root))

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"rg 执行失败，token={token}, code={result.returncode}, stderr={result.stderr.strip()}"
        )

    hits: list[Hit] = []
    for line in result.stdout.splitlines():
        parsed = _parse_rg_line(line)
        if parsed is not None:
            hits.append(parsed)
    return hits


def _iter_python_files(root: Path) -> list[Path]:
    """遍历 Python 文件。"""
    return sorted([p for p in root.rglob("*.py") if p.is_file()])


def _extract_dynamic_key_patterns(py_file: Path) -> list[tuple[str, str]]:
    """提取 get_text_patterns(f"prefix{var}suffix") 的 prefix/suffix。"""
    source = py_file.read_text(encoding="utf-8")
    tree = ast.parse(source)
    patterns: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "get_text_patterns":
            continue
        if not node.args:
            continue
        arg0 = node.args[0]
        if not isinstance(arg0, ast.JoinedStr):
            continue

        parts: list[str] = []
        for value in arg0.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{*}")
        joined = "".join(parts)
        if "{*}" not in joined:
            continue
        prefix, _, suffix = joined.partition("{*}")
        patterns.append((prefix, suffix))
    return patterns


def collect_dynamic_locale_key_usage(
    keys: list[str], source_root: Path
) -> dict[str, list[Hit]]:
    """补充动态 key 使用（例如 f"rewards_tab_{tab}"）。"""
    key_set = set(keys)
    result: dict[str, list[Hit]] = {key: [] for key in keys}
    for py_file in _iter_python_files(source_root):
        try:
            patterns = _extract_dynamic_key_patterns(py_file)
        except Exception:
            continue
        if not patterns:
            continue
        rel = str(py_file)
        for prefix, suffix in patterns:
            for key in key_set:
                if key.startswith(prefix) and key.endswith(suffix):
                    result[key].append(
                        Hit(
                            file=rel,
                            line=1,
                            content=f"dynamic:{prefix}{{*}}{suffix}",
                        )
                    )
    return result


def collect_locale_key_occurrences(
    keys: list[str],
    source_root: Path,
    include_dynamic: bool = False,
) -> dict[str, list[Hit]]:
    """统计 key 在 src/ptcgp_auto_v2 下的出现情况（排除 locales 目录）。"""
    output: dict[str, list[Hit]] = {}
    globs = ["!**/locales/**"]
    for key in keys:
        output[key] = _run_rg_quoted_token(key, source_root, globs)

    if include_dynamic:
        dynamic_hits = collect_dynamic_locale_key_usage(keys, source_root)
        for key in keys:
            if dynamic_hits[key]:
                output[key].extend(dynamic_hits[key])
    return output


def collect_template_occurrences(token: str, project_root: Path) -> list[Hit]:
    """统计模板 token 在整个项目中的出现情况（排除 docs 防文档回流污染）。"""
    globs = ["!docs/**"]
    return _run_rg_literal(token, project_root, globs)


def to_rel(path: str, root: Path) -> str:
    """转为项目相对路径。"""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(root.resolve()))
    except ValueError:
        return path


def summarize_locale(
    locale_occ: dict[str, list[Hit]],
) -> tuple[list[str], list[str]]:
    """返回已使用/可清理 key 列表。"""
    used = sorted([key for key, hits in locale_occ.items() if hits])
    removable = sorted([key for key, hits in locale_occ.items() if not hits])
    return used, removable


def classify_templates(
    template_names: list[str],
    project_root: Path,
    source_root: Path,
) -> tuple[list[str], list[str], list[str], dict[str, list[Hit]]]:
    """模板分类：v2命中 / 项目其他命中 / 全未命中。"""
    in_v2: list[str] = []
    outside_v2: list[str] = []
    never_used: list[str] = []
    all_hits: dict[str, list[Hit]] = {}

    source_prefix = source_root.resolve()
    for name in template_names:
        hits = collect_template_occurrences(name, project_root)
        all_hits[name] = hits
        if not hits:
            never_used.append(name)
            continue

        has_v2 = False
        for hit in hits:
            hit_path = Path(hit.file).resolve()
            if hit_path.is_relative_to(source_prefix):
                has_v2 = True
                break

        if has_v2:
            in_v2.append(name)
        else:
            outside_v2.append(name)

    return sorted(in_v2), sorted(outside_v2), sorted(never_used), all_hits


def print_terminal_report(
    project_root: Path,
    source_root: Path,
    locale_keys: list[str],
    locale_occ: dict[str, list[Hit]],
    template_names: list[str],
    in_v2: list[str],
    outside_v2: list[str],
    never_used: list[str],
    template_hits: dict[str, list[Hit]],
    strict_static: bool,
):
    """打印终端可读报告。"""
    used, removable = summarize_locale(locale_occ)

    print("=== Locale Key 审计 ===")
    print(f"范围: {to_rel(str(source_root), project_root)}")
    print(f"模式: {'静态字面量' if strict_static else '静态+动态推断'}")
    print(f"总 key: {len(locale_keys)}")
    print(f"已出现: {len(used)}")
    print(f"可清理(未出现): {len(removable)}")
    print("\n[可清理 key]")
    for key in removable:
        print(f"- {key}")

    print("\n=== 模板审计 ===")
    print("范围: 项目全量（排除 docs/）")
    print(f"模板总数: {len(template_names)}")
    print(f"出现在 src/ptcgp_auto_v2/: {len(in_v2)}")
    print(f"未在 src/ptcgp_auto_v2/，但在项目其他位置出现: {len(outside_v2)}")
    print(f"全项目从未使用: {len(never_used)}")

    print("\n[1) 出现在 src/ptcgp_auto_v2/]")
    for name in in_v2:
        print(f"- {name}")

    print("\n[2) 未在 src/ptcgp_auto_v2/，但在项目其他位置出现]")
    for name in outside_v2:
        examples = template_hits[name][:3]
        if examples:
            text = "，".join(
                f"{to_rel(hit.file, project_root)}:{hit.line}" for hit in examples
            )
            print(f"- {name} -> {text}")
        else:
            print(f"- {name}")

    print("\n[3) 全项目从未使用]")
    for name in never_used:
        print(f"- {name}")


def write_analysis_doc(
    output_file: Path,
    project_root: Path,
    locale_file: Path,
    source_root: Path,
    removable_keys: list[str],
    in_v2: list[str],
    outside_v2: list[str],
    never_used: list[str],
):
    """写入精简可读文档（非程序原始输出）。"""
    lines: list[str] = []
    lines.append("# Locale 与模板审查（人工整理）")
    lines.append("")
    lines.append("## 结论")
    lines.append(f"- locale 审计文件：`{to_rel(str(locale_file), project_root)}`")
    lines.append(f"- 检索范围：`{to_rel(str(source_root), project_root)}`")
    lines.append(f"- 可清理 locale key：**{len(removable_keys)}**")
    lines.append(f"- 模板在 v2 中使用：**{len(in_v2)}**")
    lines.append(f"- 模板仅在 v2 外使用：**{len(outside_v2)}**")
    lines.append(f"- 模板全项目未使用：**{len(never_used)}**")
    lines.append("")

    lines.append("## 可清理 locale key")
    if removable_keys:
        for key in removable_keys:
            lines.append(f"- `{key}`")
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("## 模板分类")
    lines.append("### 出现在 src/ptcgp_auto_v2/")
    for name in in_v2:
        lines.append(f"- `{name}`")
    if not in_v2:
        lines.append("- 无")
    lines.append("")

    lines.append("### 未出现在 src/ptcgp_auto_v2/（但项目其他位置有）")
    for name in outside_v2:
        lines.append(f"- `{name}`")
    if not outside_v2:
        lines.append("- 无")
    lines.append("")

    lines.append("### 全项目从未使用")
    for name in never_used:
        lines.append(f"- `{name}`")
    if not never_used:
        lines.append("- 无")
    lines.append("")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """解析参数。"""
    parser = argparse.ArgumentParser(description="使用 rg 审计 locale key 与模板引用")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="项目根目录",
    )
    parser.add_argument(
        "--locale-file",
        type=Path,
        default=Path("src/ptcgp_auto_v2/locales/zh_Hant.py"),
        help="locale 文件（相对 project-root）",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("src/ptcgp_auto_v2"),
        help="源码检索目录（相对 project-root）",
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path("templates"),
        help="模板目录（相对 project-root）",
    )
    parser.add_argument(
        "--write-doc",
        action="store_true",
        help="把人工可读结论文档写入 docs/refs",
    )
    parser.add_argument(
        "--doc-file",
        type=Path,
        default=Path("docs/refs/12-locale-template-usage-audit.md"),
        help="输出文档路径（相对 project-root）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="在终端额外输出 JSON 结果",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="清理 zh_Hant 未使用 key，并把其他 locale 强制对齐到 zh_Hant",
    )
    parser.add_argument(
        "--sort",
        action="store_true",
        help="重排所有 locale key 为字母序并清除注释行（通过重写实现）",
    )
    parser.add_argument(
        "--include-dynamic",
        action="store_true",
        help='把 get_text_patterns(f"...") 的动态 key 推断也计入使用',
    )
    return parser.parse_args()


def ensure_rg_available():
    """检查 rg 是否可用。"""
    result = subprocess.run(["rg", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("未检测到 rg，请先安装 ripgrep")


def main():
    """脚本入口。"""
    args = parse_args()
    ensure_rg_available()

    project_root = args.project_root.resolve()
    locale_file = (project_root / args.locale_file).resolve()
    source_root = (project_root / args.source_root).resolve()
    templates_dir = (project_root / args.templates_dir).resolve()

    locale_keys = extract_locale_keys(locale_file)
    locale_occ = collect_locale_key_occurrences(
        locale_keys,
        source_root,
        include_dynamic=args.include_dynamic,
    )

    template_names = extract_template_names(templates_dir)
    in_v2, outside_v2, never_used, template_hits = classify_templates(
        template_names,
        project_root,
        source_root,
    )

    print_terminal_report(
        project_root=project_root,
        source_root=source_root,
        locale_keys=locale_keys,
        locale_occ=locale_occ,
        template_names=template_names,
        in_v2=in_v2,
        outside_v2=outside_v2,
        never_used=never_used,
        template_hits=template_hits,
        strict_static=not args.include_dynamic,
    )

    used, removable = summarize_locale(locale_occ)
    if args.json:
        payload = {
            "locale": {
                "total": len(locale_keys),
                "used": len(used),
                "removable": removable,
            },
            "templates": {
                "total": len(template_names),
                "in_v2": in_v2,
                "outside_v2": outside_v2,
                "never_used": never_used,
            },
        }
        print("\n=== JSON ===")
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.write_doc:
        output_file = (project_root / args.doc_file).resolve()
        write_analysis_doc(
            output_file=output_file,
            project_root=project_root,
            locale_file=locale_file,
            source_root=source_root,
            removable_keys=removable,
            in_v2=in_v2,
            outside_v2=outside_v2,
            never_used=never_used,
        )
        print(f"\n文档已写入: {to_rel(str(output_file), project_root)}")

    if args.clean or args.sort:
        locales_dir = locale_file.parent
        locale_files = list_locale_files(locales_dir)
        print(f"\n仅处理 v2 locale 目录: {to_rel(str(locales_dir), project_root)}")

        constants_file = project_root / "src/ptcgp_auto_v2/config/constants.py"
        supported_locales, locale_to_ocr = load_locale_support_from_constants(
            constants_file
        )
        if not supported_locales:
            supported_locales = [locale_file.stem]
        if locale_file.stem not in supported_locales:
            supported_locales = [locale_file.stem] + supported_locales
        print("支持语言映射（locale -> ocr）:")
        for locale_name in supported_locales:
            ocr_name = locale_to_ocr.get(locale_name, "<未配置>")
            print(f"- {locale_name} -> {ocr_name}")

        keep_keys = set(locale_keys)
        if args.clean:
            _, removable = summarize_locale(locale_occ)
            keep_keys = set(locale_keys) - set(removable)

        if args.sort:
            clean_and_sort_locale_file(
                locale_file=locale_file,
                keep_keys=keep_keys,
                sort_keys=True,
            )
        elif args.clean:
            _remove_keys_preserve_layout(locale_file, set(locale_keys) - keep_keys)

        zh_dict = load_text_patterns_dict(locale_file)
        created = ensure_supported_locale_files(
            locales_dir=locales_dir,
            supported_locales=supported_locales,
            base_dict=zh_dict,
            sort_keys=args.sort,
        )
        if created:
            print("自动生成 locale 文件:")
            for created_file in created:
                print(f"- {to_rel(str(created_file), project_root)}")

        locale_files = list_locale_files(locales_dir)
        for file in locale_files:
            if file.resolve() == locale_file.resolve():
                continue
            if file.stem not in supported_locales:
                continue
            align_locale_file_to_base(
                locale_file=file,
                base_dict=zh_dict,
                sort_keys=args.sort,
            )
        print("\n已执行 locale 清理/排序/对齐")


if __name__ == "__main__":
    main()

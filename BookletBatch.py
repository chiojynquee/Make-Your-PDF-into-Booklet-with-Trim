#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDF 小册子自动拼版工具（Windows 控制台版）

依赖：Coherent PDF 的 cpdf 和 pdfcpu；不需要安装第三方 Python 包。

模式 1：原始 PDF -> 按 4/8/12/16 页拆分 -> 拼版 -> 8 mm 边距 -> 裁切线
模式 2：已拆分 PDF（单个文件或文件夹） -> 拼版 -> 8 mm 边距 -> 裁切线
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence


CHUNK_OPTIONS = {"4", "8", "12", "16"}


def clean_input(value: str) -> str:
    """去掉用户复制路径时可能带上的首尾引号。"""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value


def natural_sort_key(path: Path) -> list[object]:
    """按文件名中的数字自然排序，避免 split100 排在 split20 前面。"""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", path.name)]


def resolve_tool(tool_name: str) -> str:
    """从 PATH 定位工具；找不到时允许输入 exe 完整路径。"""
    found = shutil.which(tool_name) or shutil.which(f"{tool_name}.exe")
    if found:
        return str(Path(found).resolve())

    while True:
        answer = clean_input(input(
            f"找不到 {tool_name}。请输入 {tool_name}.exe 的完整路径，"
            "或先把它加入 Windows PATH：\n> "
        ))
        if not answer:
            continue

        candidate = Path(answer).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())

        found = shutil.which(answer) or shutil.which(f"{answer}.exe")
        if found:
            return str(Path(found).resolve())

        print(f"没有找到该文件或命令：{answer}\n", file=sys.stderr)


def command_display(command: Sequence[str]) -> str:
    """以适合当前系统的形式显示即将执行的命令。"""
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)


def run_external(executable: str, arguments: Sequence[str], step: str) -> None:
    """运行外部工具。参数以列表传递，因此路径有空格也无需 shell 引号。"""
    command = [executable, *[str(arg) for arg in arguments]]
    print(f"\n>>> {step}")
    print(f"    {command_display(command)}")
    try:
        result = subprocess.run(command, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError(f"无法启动外部程序：{executable}") from exc
    except OSError as exc:
        raise RuntimeError(f"启动程序失败：{exc}") from exc

    if result.returncode != 0:
        raise RuntimeError(f"{step}失败，程序退出代码：{result.returncode}。请检查上方工具输出。")


def assert_output_file(path: Path, step: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{step}已执行，但没有生成文件：{path}")
    if path.stat().st_size <= 0:
        raise RuntimeError(f"{step}生成了空文件：{path}")


def unique_output_root(requested: str, default_path: Path) -> Path:
    """输出目录存在时使用 _001、_002 等新目录，避免覆盖旧文件。"""
    raw = clean_input(requested)
    candidate = Path(raw).expanduser() if raw else default_path
    candidate = candidate.resolve()

    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        alternate = Path(f"{candidate}_{counter:03d}")
        if not alternate.exists():
            print(f"输出目录已存在，为避免覆盖，改用：{alternate}")
            return alternate
        counter += 1


def process_one_pdf(
    source_pdf: Path,
    index: int,
    booklet_dir: Path,
    final_dir: Path,
    temp_dir: Path,
    cpdf_path: str,
    pdfcpu_path: str,
) -> None:
    number = f"{index:03d}"
    booklet_pdf = booklet_dir / f"booklet{number}.pdf"
    final_pdf = final_dir / f"final{number}.pdf"
    temp1 = temp_dir / f"temp1_{number}.pdf"
    temp2 = temp_dir / f"temp2_{number}.pdf"

    print(f"\n[{index}] 正在处理：{source_pdf}")

    # 按用户已验证的命令顺序执行 2-up 小册子拼版。
    run_external(
        pdfcpu_path,
        ["booklet", str(booklet_pdf), "2", str(source_pdf)],
        f"拼版：{source_pdf.name}",
    )
    assert_output_file(booklet_pdf, "拼版")

    run_external(
        cpdf_path,
        ["-frombox", "/MediaBox", "-tobox", "/TrimBox", "-mediabox-if-missing",
         str(booklet_pdf), "-o", str(temp1)],
        "设置 TrimBox",
    )
    assert_output_file(temp1, "设置 TrimBox")

    # 保留原流程：pdfcpu 以 mm 为单位向外扩展 8 mm。
    run_external(
        pdfcpu_path,
        ["crop", "-u", "mm", "--", "-8", str(temp1), str(temp2)],
        "增加 8 mm 边距",
    )
    assert_output_file(temp2, "增加 8 mm 边距")

    run_external(
        cpdf_path,
        ["-trim-marks", str(temp2), "-o", str(final_pdf)],
        "添加裁切线",
    )
    assert_output_file(final_pdf, "添加裁切线")

    print(f"拼版文件：{booklet_pdf}")
    print(f"最终文件：{final_pdf}")


def prompt_mode() -> str:
    print("\n=========================================")
    print("       PDF 小册子自动拼版工具")
    print("=========================================")
    print("1. 原始 PDF（按每册页数拆分，再逐册拼版）")
    print("2. 已拆分 PDF（输入单个 PDF，或包含多个 PDF 的文件夹）")
    while True:
        mode = input("\n请选择模式 1/2：").strip()
        if mode in {"1", "2"}:
            return mode
        print("请输入 1 或 2。")


def collect_sources(mode: str, input_path: Path) -> tuple[list[Path], Path, Path, int | None]:
    """校验输入并返回源文件列表、默认输出目录和输入路径信息。"""
    if not input_path.exists():
        raise RuntimeError(f"路径不存在：{input_path}")

    if mode == "1":
        if not input_path.is_file():
            raise RuntimeError("原始 PDF 模式必须输入单个 PDF 文件，而不是文件夹。")
        if input_path.suffix.lower() != ".pdf":
            raise RuntimeError("输入文件扩展名不是 .pdf。")

        print("\n可选每册页数：4 / 8 / 12 / 16（默认 16）")
        while True:
            chunk_text = input("每册页数 [16]：").strip()
            if not chunk_text:
                chunk_pages = 16
                break
            if chunk_text in CHUNK_OPTIONS:
                chunk_pages = int(chunk_text)
                break
            print("请输入 4、8、12 或 16。")

        default_output = input_path.parent / f"{input_path.stem}_booklet_output"
        return [], default_output, input_path, chunk_pages

    # 已拆分模式支持单个 PDF 或文件夹顶层的多个 PDF。
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            raise RuntimeError("输入文件扩展名不是 .pdf。")
        sources = [input_path]
        default_output = input_path.parent / f"{input_path.stem}_booklet_output"
    elif input_path.is_dir():
        sources = sorted(
            (item for item in input_path.iterdir()
             if item.is_file() and item.suffix.lower() == ".pdf"),
            key=natural_sort_key,
        )
        if not sources:
            raise RuntimeError(f"该文件夹顶层没有 PDF 文件：{input_path}")
        default_output = input_path.parent / f"{input_path.name}_booklet_output"
    else:
        raise RuntimeError("输入路径既不是 PDF 文件，也不是文件夹。")

    return sources, default_output, input_path, None


def main() -> int:
    try:
        mode = prompt_mode()
        input_text = clean_input(input(
            "请输入 PDF 文件路径；已拆分模式也可以输入包含多个 PDF 的文件夹路径：\n> "
        ))
        if not input_text:
            raise RuntimeError("没有输入路径。")

        input_path = Path(input_text).expanduser().resolve()
        source_files, default_output, input_path, chunk_pages = collect_sources(mode, input_path)

        cpdf_path = resolve_tool("cpdf")
        pdfcpu_path = resolve_tool("pdfcpu")

        output_text = input(
            f"\n输出目录（直接回车使用默认值：{default_output}）：\n> "
        )
        output_root = unique_output_root(output_text, default_output)

        # 只在输出目录为新路径时创建，避免触碰已经存在的结果。
        output_root.mkdir(parents=True, exist_ok=False)
        booklet_dir = output_root / "booklet"
        final_dir = output_root / "final"
        booklet_dir.mkdir()
        final_dir.mkdir()

        if mode == "1":
            split_dir = output_root / "split"
            split_dir.mkdir()

        # 中间临时 PDF 自动放进系统临时目录；无论成功或失败都会清理。
        with tempfile.TemporaryDirectory(prefix="BookletBatch_") as temporary_name:
            temp_dir = Path(temporary_name)

            if mode == "1":
                assert chunk_pages is not None
                # cpdf 的 %% 模式编号遵循原有命令写法，例如 split01.pdf、split02.pdf。
                split_pattern = split_dir / "split%%.pdf"
                run_external(
                    cpdf_path,
                    [str(input_path), "-split", "-chunk", str(chunk_pages), "-o", str(split_pattern)],
                    f"按每册 {chunk_pages} 页拆分原始 PDF",
                )
                source_files = sorted(
                    (item for item in split_dir.iterdir()
                     if item.is_file() and item.suffix.lower() == ".pdf"),
                    key=natural_sort_key,
                )
                if not source_files:
                    raise RuntimeError(
                        "cpdf 执行后没有找到拆分文件。请确认 cpdf 的 -split 输出文件名模式是否受当前版本支持。"
                    )
                print(f"拆分完成：共 {len(source_files)} 册。")

            for index, source_pdf in enumerate(source_files, start=1):
                process_one_pdf(
                    source_pdf=source_pdf,
                    index=index,
                    booklet_dir=booklet_dir,
                    final_dir=final_dir,
                    temp_dir=temp_dir,
                    cpdf_path=cpdf_path,
                    pdfcpu_path=pdfcpu_path,
                )

        print("\n=========================================")
        print("全部处理完成！")
        print(f"输出目录：{output_root}")
        if mode == "1":
            print(f"拆分文件：{output_root / 'split'}")
        print(f"拼版文件：{booklet_dir}")
        print(f"最终文件：{final_dir}")
        return 0

    except KeyboardInterrupt:
        print("\n用户取消操作。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"\n处理失败：{exc}", file=sys.stderr)
        print("请根据上方提示检查路径、工具安装情况和工具输出。", file=sys.stderr)
        return 1
    finally:
        try:
            input("\n按 Enter 键退出...")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FWT - File Wash & Transform
视频文件洗码混淆工具，用于安全上传至网盘。
"""

import argparse
import os
import sys

# 确保当前目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import (
    process_directory, restore_directory,
    process_directory_wash, restore_directory_wash,
    print_stats,
    FWT_EXT, VIDEO_EXTENSIONS, HEADER_XOR_LEN, PADDING_LEN, WASH_PADDING,
)
from preview import extract_previews


def cmd_process(args):
    """处理模式。"""
    input_dir = os.path.abspath(args.input)
    if not os.path.isdir(input_dir):
        print(f"错误: 目录不存在: {input_dir}")
        sys.exit(1)

    if args.mode == 'wash':
        # ── wash 模式：轻量洗码 ──
        print("╔══════════════════════════════════════╗")
        print("║    FWT - 轻量洗码模式 (wash)         ║")
        print("╚══════════════════════════════════════╝")
        print(f"仅追加 {WASH_PADDING}B 随机数，文件保留原名\n")

        exts = None
        if args.ext:
            exts = set(e.lower() if e.startswith('.') else '.' + e.lower() for e in args.ext)
            print(f"限定扩展名: {', '.join(sorted(exts))}")

        stats = process_directory_wash(input_dir, output_dir=args.output, extensions=exts)
        print_stats(stats, 'wash')

        if stats['washed'] > 0:
            actual_out = args.output if args.output else input_dir + '_washed'
            print(f"\n洗码完成！输出目录: {actual_out}")
    else:
        # ── obfuscate 模式（默认）──
        print("╔══════════════════════════════════════╗")
        print("║     FWT - 混淆处理模式 (obfuscate)  ║")
        print("╚══════════════════════════════════════╝")
        print(f"混淆字节: {HEADER_XOR_LEN}B | 洗码字节: {PADDING_LEN}B | 后缀: {FWT_EXT}")
        print(f"视频格式: {len(VIDEO_EXTENSIONS)} 种 | 其他文件 → 原样复制")
        print(f"生成预览: {'是' if not args.no_preview else '否'}")

        stats = process_directory(input_dir, output_dir=args.output, gen_preview=not args.no_preview)
        print_stats(stats, 'process')

        if stats['video_processed'] > 0:
            actual_out = args.output if args.output else os.path.join(
                os.path.dirname(os.path.abspath(input_dir.rstrip(os.sep + '/'))),
                os.path.basename(input_dir.rstrip(os.sep + '/')) + '_washed'
            )
            print(f"\n处理完成！输出目录: {actual_out}")
            print("请将输出目录整个上传至网盘即可。")
        if stats['preview_generated'] > 0:
            print("下载预览 zip 后可运行 'fwt.py preview -i <zip或目录>' 查看。")


def cmd_restore(args):
    """还原模式。"""
    input_dir = os.path.abspath(args.input)
    if not os.path.isdir(input_dir):
        print(f"错误: 目录不存在: {input_dir}")
        sys.exit(1)

    if args.mode == 'wash':
        # ── wash 还原：截掉所有文件末尾 5B ──
        print("╔══════════════════════════════════════╗")
        print("║   FWT - 轻量洗码还原 (unwash)        ║")
        print("╚══════════════════════════════════════╝")
        print("将截掉每个文件末尾 5 字节，输出到 _restored 目录\n")

        stats = restore_directory_wash(input_dir, output_dir=args.output)
        print_stats(stats, 'unwash')

        if stats['restored'] > 0:
            actual_out = args.output if args.output else input_dir + '_restored'
            print(f"\n还原完成！输出目录: {actual_out}")
    else:
        # ── obfuscate 还原 ──
        print("╔══════════════════════════════════════╗")
        print("║     FWT - 混淆文件还原 (obfuscate)  ║")
        print("╚══════════════════════════════════════╝")

        stats = restore_directory(input_dir)
        print_stats(stats, 'restore')

        if stats['restored'] > 0:
            print(f"\n还原完成！已还原 {stats['restored']} 个文件到原目录，.fwt 已删除。")


def cmd_preview(args):
    """预览模式：解压预览 ZIP 包。"""
    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        print(f"错误: 路径不存在: {input_path}")
        sys.exit(1)

    print("╔══════════════════════════════════════╗")
    print("║        FWT - 预览解压模式           ║")
    print("╚══════════════════════════════════════╝")

    stats = extract_previews(input_path)
    print(f"\n解压完成: {stats['extracted']} 成功, {stats['failed']} 失败")

    if stats['failed'] > 0:
        print("\n提示: 解压失败可能是因为未安装 pyzipper 库。")
        print("请运行: pip install pyzipper")


def main():
    parser = argparse.ArgumentParser(
        description='FWT - File Wash & Transform :: 视频洗码混淆工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  fwt.py process -i D:\\Videos                       处理视频目录(混淆+洗码)
  fwt.py process -i D:\\Videos --no-preview           处理但不生成预览包
  fwt.py process -i D:\\Videos -m wash                轻量洗码(仅追加5B随机数)
  fwt.py process -i D:\\Videos -m wash --ext mp4 mkv  仅洗码mp4/mkv文件
  fwt.py restore -i D:\\Videos_washed                 还原.fwt文件为原始视频
  fwt.py restore -i D:\\Videos_washed -m wash         还原wash模式(截掉末尾5B)
  fwt.py preview -i D:\\Videos_washed                 解压目录中所有预览ZIP
  fwt.py preview -i preview.zip                      解压单个预览ZIP
        """,
    )
    sub = parser.add_subparsers(dest='command', help='运行模式')

    # ── process ──
    p = sub.add_parser('process', help='处理文件')
    p.add_argument('-i', '--input', required=True, help='输入目录路径')
    p.add_argument('-o', '--output', default=None, help='输出目录路径')
    p.add_argument('-m', '--mode', choices=['obfuscate', 'wash'], default='obfuscate',
                   help='处理模式: obfuscate=混淆+洗码(默认), wash=仅追加5B随机数')
    p.add_argument('--ext', nargs='+', default=None,
                   help='wash 模式下限定处理的扩展名，如 .mp4 .mkv（不指定=全部文件）')
    p.add_argument('--no-preview', action='store_true', help='不生成预览ZIP包 (仅obfuscate模式)')
    p.set_defaults(func=cmd_process)

    # ── restore ──
    r = sub.add_parser('restore', help='还原文件')
    r.add_argument('-i', '--input', required=True, help='输入目录路径')
    r.add_argument('-o', '--output', default=None, help='输出目录路径 (wash模式; 默认输入目录_restored)')
    r.add_argument('-m', '--mode', choices=['obfuscate', 'wash'], default='obfuscate',
                   help='还原模式: obfuscate=还原.fwt文件(默认), wash=截掉末尾5B')

    # ── preview ──
    v = sub.add_parser('preview', help='解压预览 ZIP 包查看截图/GIF')
    v.add_argument('-i', '--input', required=True, help='预览 ZIP 文件或包含预览 ZIP 的目录')
    v.set_defaults(func=cmd_preview)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n\n操作已取消。")
        sys.exit(1)


if __name__ == '__main__':
    main()

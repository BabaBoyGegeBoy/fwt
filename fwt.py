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
    process_directory, restore_directory, print_stats,
    FWT_EXT, VIDEO_EXTENSIONS, HEADER_XOR_LEN, PADDING_LEN,
)
from preview import extract_previews


def cmd_process(args):
    """处理模式：洗码 + 混淆 + 生成预览包。"""
    input_dir = os.path.abspath(args.input)
    if not os.path.isdir(input_dir):
        print(f"错误: 目录不存在: {input_dir}")
        sys.exit(1)

    print("╔══════════════════════════════════════╗")
    print("║        FWT - 文件处理模式           ║")
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
    """还原模式：扫描 .fwt 文件并还原为原始视频。"""
    input_dir = os.path.abspath(args.input)
    if not os.path.isdir(input_dir):
        print(f"错误: 目录不存在: {input_dir}")
        sys.exit(1)

    print("╔══════════════════════════════════════╗")
    print("║        FWT - 文件还原模式           ║")
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
  fwt.py process -i D:\\Videos      处理视频目录，输出到 Videos_washed
  fwt.py process -i D:\\Videos --no-preview   处理但不生成预览包
  fwt.py restore -i D:\\Videos_washed        还原 .fwt 文件为原始视频
  fwt.py preview -i D:\\Videos_washed         解压目录中所有预览 ZIP
  fwt.py preview -i preview.zip              解压单个预览 ZIP
        """,
    )
    sub = parser.add_subparsers(dest='command', help='运行模式')

    # ── process ──
    p = sub.add_parser('process', help='处理视频 → 输出 _washed 目录')
    p.add_argument('-i', '--input', required=True, help='输入视频目录路径')
    p.add_argument('-o', '--output', default=None, help='输出目录路径（默认为输入目录_washed）')
    p.add_argument('--no-preview', action='store_true', help='不生成预览ZIP包')
    p.set_defaults(func=cmd_process)

    # ── restore ──
    r = sub.add_parser('restore', help='还原 .fwt 文件为原始视频（原地+清理）')
    r.add_argument('-i', '--input', required=True, help='包含 .fwt 文件的目录路径')
    r.set_defaults(func=cmd_restore)

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

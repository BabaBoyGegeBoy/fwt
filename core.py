# -*- coding: utf-8 -*-
"""
FWT Core - 文件处理核心逻辑。
负责：视频文件头混淆、MD5洗码、元数据写入、还原。
"""

import base64
import json
import os
import shutil
import struct

# 兼容直接运行和包导入两种方式
try:
    from preview import generate_preview
except ImportError:
    try:
        from .preview import generate_preview
    except ImportError:
        generate_preview = None  # type: ignore

# ── 常量 ──────────────────────────────────────────────
HEADER_XOR_LEN = 128          # 混淆文件头字节数
PADDING_LEN    = 5            # MD5洗码追加随机字节数
MAGIC          = b'FWT1'      # 文件尾部魔数标记
FWT_EXT        = '.fwt'       # 处理后文件后缀
TORRENT_EXT    = '.torrent'   # 种子文件后缀

# 常见视频格式（全部）
VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.mov', '.avi', '.wmv', '.flv', '.webm',
    '.ts', '.m4v', '.3gp', '.rmvb', '.rm', '.vob', '.ogv',
    '.mts', '.m2ts', '.asf', '.divx', '.xvid', '.f4v',
    '.mpeg', '.mpg', '.mpe', '.m2v', '.dat', '.swf',
}


# ── 文件处理 ──────────────────────────────────────────

def process_file(input_path: str, output_path: str) -> dict:
    """
    处理单个文件：混淆文件头 + 追加随机字节 + 写入元数据尾部。

    返回: {'success': bool, 'orig_size': int, 'new_size': int, 'error': str|None}
    """
    orig_ext = os.path.splitext(input_path)[1].lower()
    orig_size = os.path.getsize(input_path)

    # 确定实际混淆字节数（文件可能极小）
    hlen = min(HEADER_XOR_LEN, orig_size)
    xor_key = os.urandom(hlen)

    try:
        with open(input_path, 'rb') as fin, open(output_path, 'wb') as fout:
            # 1. 读文件头、XOR 混淆后写入
            if hlen > 0:
                header = bytearray(fin.read(hlen))
                for i in range(hlen):
                    header[i] ^= xor_key[i]
                fout.write(header)

            # 2. 复制剩余内容
            shutil.copyfileobj(fin, fout)

            # 3. 追加 5 字节随机数（MD5 洗码）
            padding = os.urandom(PADDING_LEN)
            fout.write(padding)

            # 4. 构建尾部元数据
            metadata = {
                'v': 1,
                'ext': orig_ext,
                'hlen': hlen,
                'hkey': base64.b64encode(xor_key).decode('ascii'),
            }
            json_bytes = json.dumps(metadata, separators=(',', ':')).encode('utf-8')

            # 5. 写入尾部：MAGIC(4) + JSON + json_len(2)
            #    json_len 在最后，保证文件末尾 2 字节就是长度值
            fout.write(MAGIC)
            fout.write(json_bytes)
            fout.write(struct.pack('>H', len(json_bytes)))

        new_size = os.path.getsize(output_path)
        return {'success': True, 'orig_size': orig_size, 'new_size': new_size, 'error': None}

    except Exception as e:
        # 清理可能写了一半的文件
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        return {'success': False, 'orig_size': orig_size, 'new_size': 0, 'error': str(e)}


def restore_file(input_path: str) -> dict:
    """
    原地还原 .fwt 文件：恢复文件头 → 去除尾部 → 写回原后缀 → 删除 .fwt。

    返回: {'success': bool, 'output': str, 'error': str|None}
    """
    file_size = os.path.getsize(input_path)

    try:
        with open(input_path, 'rb') as f:
            # ── 解析尾部 ──
            # 尾部结构：[PADDING][MAGIC:4][json_len:2][JSON]
            f.seek(-2, os.SEEK_END)
            json_len_b = f.read(2)
            if len(json_len_b) < 2:
                return {'success': False, 'output': '', 'error': '文件不完整，无法读取元数据'}
            json_len = struct.unpack('>H', json_len_b)[0]

            footer_size = 4 + 2 + json_len  # MAGIC + len + JSON

            f.seek(-2 - json_len, os.SEEK_END)
            json_bytes = f.read(json_len)
            metadata = json.loads(json_bytes)

            f.seek(-2 - json_len - 4, os.SEEK_END)
            magic = f.read(4)
            if magic != MAGIC:
                return {'success': False, 'output': '', 'error': f'不是有效的 FWT 文件（魔数不匹配）'}

            # ── 读取原始内容 ──
            orig_content_size = file_size - PADDING_LEN - footer_size
            if orig_content_size <= 0:
                return {'success': False, 'output': '', 'error': '文件数据异常'}

            f.seek(0)
            content = bytearray(f.read(orig_content_size))

        # ── 恢复文件头 ──
        hkey = base64.b64decode(metadata['hkey'])
        hlen = min(metadata['hlen'], len(content))
        for i in range(hlen):
            content[i] ^= hkey[i]

    except json.JSONDecodeError:
        return {'success': False, 'output': '', 'error': '元数据解析失败'}
    except Exception as e:
        return {'success': False, 'output': '', 'error': str(e)}

    # ── 写入还原文件 ──
    output_dir = os.path.dirname(input_path)
    output_name = os.path.splitext(os.path.basename(input_path))[0] + metadata['ext']
    output_path = os.path.join(output_dir, output_name)

    # 避免覆盖已有同名文件
    counter = 1
    while os.path.exists(output_path):
        base, ext = os.path.splitext(output_name)
        output_path = os.path.join(output_dir, f"{base}_{counter}{ext}")
        counter += 1

    try:
        with open(output_path, 'wb') as f:
            f.write(content)
    except Exception as e:
        return {'success': False, 'output': '', 'error': f'写入还原文件失败: {e}'}

    # ── 删除 .fwt ──
    try:
        os.remove(input_path)
    except OSError as e:
        return {'success': True, 'output': output_path, 'error': f'还原成功，但删除 .fwt 失败: {e}'}

    return {'success': True, 'output': output_path, 'error': None}


# ── 批量处理 ──────────────────────────────────────────

def _build_output_dir(input_dir: str) -> str:
    """根据输入目录构建输出目录路径（同级 + '_washed'）。"""
    abs_in = os.path.abspath(input_dir).rstrip(os.sep + '/')
    parent = os.path.dirname(abs_in)
    name = os.path.basename(abs_in)
    return os.path.join(parent, name + '_washed')


def process_directory(input_dir: str, output_dir: str = None, gen_preview: bool = True) -> dict:
    """
    批量处理目录：
    - 视频文件 → 处理为 .fwt 并生成预览 zip
    - 其他文件 → 按目录结构原样复制

    返回统计信息。
    """
    if output_dir is None:
        output_dir = _build_output_dir(input_dir)
    else:
        output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    stats = {
        'video_processed': 0,
        'video_failed':   0,
        'files_copied':    0,
        'preview_generated': 0,
        'preview_failed':  0,
        'skipped':         0,
        'errors':          [],
    }

    print(f"\n输入目录: {input_dir}")
    print(f"输出目录: {output_dir}\n")

    for root, dirs, files in os.walk(input_dir):
        # 构建相对路径
        rel = os.path.relpath(root, input_dir)
        if rel == '.':
            rel = ''

        out_root = os.path.join(output_dir, rel)
        os.makedirs(out_root, exist_ok=True)

        for filename in files:
            src_path = os.path.join(root, filename)
            ext = os.path.splitext(filename)[1].lower()

            if ext in VIDEO_EXTENSIONS:
                # ── 处理视频文件 ──
                out_name = os.path.splitext(filename)[0] + FWT_EXT
                out_path = os.path.join(out_root, out_name)

                print(f"[处理] {src_path}")
                result = process_file(src_path, out_path)

                if result['success']:
                    stats['video_processed'] += 1
                    size_change = result['new_size'] - result['orig_size']
                    print(f"       → {out_name} (大小变化: +{size_change}B)")

                    # 生成预览
                    if gen_preview and generate_preview:
                        prev_result = generate_preview(src_path, out_root)
                        if prev_result['success']:
                            stats['preview_generated'] += 1
                            print(f"       → 预览: {os.path.basename(prev_result['zip_path'])}")
                        else:
                            stats['preview_failed'] += 1
                            print(f"       → 预览生成失败: {prev_result['error']}")
                else:
                    stats['video_failed'] += 1
                    stats['errors'].append((src_path, result['error']))
                    print(f"       → 失败: {result['error']}")

            else:
                # ── 复制其他文件（种子、压缩包等） ──
                dst_path = os.path.join(out_root, filename)
                print(f"[复制] {src_path}")
                shutil.copy2(src_path, dst_path)
                stats['files_copied'] += 1

    return stats


def restore_directory(input_dir: str) -> dict:
    """
    批量还原目录中所有 .fwt 文件，原地还原 + 删除 .fwt。
    """
    stats = {
        'restored': 0,
        'failed':   0,
        'errors':   [],
    }

    print(f"\n还原目录: {input_dir}\n")

    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if not filename.lower().endswith(FWT_EXT):
                continue

            src_path = os.path.join(root, filename)
            print(f"[还原] {src_path}")
            result = restore_file(src_path)

            if result['success']:
                stats['restored'] += 1
                print(f"       → {os.path.basename(result['output'])} (已删除 .fwt)")
            else:
                stats['failed'] += 1
                stats['errors'].append((src_path, result['error']))
                print(f"       → 失败: {result['error']}")

    return stats


def print_stats(stats: dict, mode: str):
    """统一打印统计信息。"""
    print("\n" + "=" * 60)

    if mode == 'process':
        print(f"视频处理: {stats['video_processed']} 成功, {stats['video_failed']} 失败")
        print(f"预览生成: {stats['preview_generated']} 成功, {stats['preview_failed']} 失败")
        print(f"文件复制: {stats['files_copied']}")
    elif mode == 'restore':
        print(f"还原成功: {stats['restored']}")
        print(f"还原失败: {stats['failed']}")

    if stats.get('errors'):
        print(f"\n错误详情:")
        for path, err in stats['errors']:
            print(f"  - {path}: {err}")

    print("=" * 60)

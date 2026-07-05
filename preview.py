# -*- coding: utf-8 -*-
"""
FWT Preview - 预览功能模块。
负责：视频截图 + GIF 生成 + 加密 ZIP 打包 + 预览包解压。
"""

import os
import re
import shutil
import string
import subprocess
import secrets
import tempfile

# ── 常量 ──────────────────────────────────────────────
SCREENSHOT_PCTS  = [10, 30, 50, 70, 90]   # 截图位置（%）
GIF_DURATION     = 4                       # GIF 时长（秒）
GIF_FPS          = 8                       # GIF 帧率
GIF_WIDTH        = 360                     # GIF 缩放宽度
PREVIEW_ZIP_RE   = re.compile(r'^（([^）]+)）【预览】(.+)\.zip$')

# ── 工具函数 ──────────────────────────────────────────

def _find_ffmpeg() -> str | None:
    """查找 ffmpeg 可执行文件路径。"""
    # 先尝试 PATH
    for name in ('ffmpeg', 'ffmpeg.exe'):
        if shutil.which(name):
            return name
    # 常见安装路径
    common_paths = [
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\ffmpeg\bin\ffmpeg.exe'),
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    return None


def _get_video_duration(video_path: str) -> float | None:
    """获取视频时长（秒）。"""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return None

    cmd = [
        ffmpeg, '-i', video_path,
        '-f', 'null', '-'
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding='utf-8',
            errors='replace',
        )
        # 从 stderr 中解析 Duration
        output = result.stderr
        match = re.search(r'Duration:\s*(\d+):(\d+):(\d+)\.(\d+)', output)
        if match:
            h, m, s, ms = map(int, match.groups())
            return h * 3600 + m * 60 + s + ms / 100.0
    except Exception:
        pass
    return None


def _extract_frame(video_path: str, time_sec: float, output_path: str) -> bool:
    """在指定时间点提取一帧保存为 JPG。"""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return False

    cmd = [
        ffmpeg, '-ss', str(time_sec),
        '-i', video_path,
        '-vframes', '1',
        '-q:v', '3',
        '-y',
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except subprocess.CalledProcessError:
        return False


def _extract_gif(video_path: str, duration: float, output_path: str) -> bool:
    """从视频中间截取 GIF。"""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return False

    mid = duration / 2
    start = max(0, mid - GIF_DURATION / 2)

    cmd = [
        ffmpeg,
        '-ss', str(start),
        '-t', str(GIF_DURATION),
        '-i', video_path,
        '-vf', (
            f'fps={GIF_FPS},'
            f'scale={GIF_WIDTH}:-1:flags=lanczos,'
            f'split[s0][s1];'
            f'[s0]palettegen=max_colors=128[p];'
            f'[s1][p]paletteuse=dither=bayer:bayer_scale=3'
        ),
        '-loop', '0',
        '-y',
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except subprocess.CalledProcessError:
        return False


def _generate_password(length: int = 8) -> str:
    """生成随机密码字符串（字母+数字）。"""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def _create_encrypted_zip(zip_path: str, password: str, files: list[str], base_dir: str) -> bool:
    """创建带密码的 ZIP 压缩包。

    使用 pyzipper 库（AES-256 加密），如未安装则回退到带注释的普通 zip。
    """
    try:
        import pyzipper
        with pyzipper.AESZipFile(
            zip_path, 'w',
            compression=pyzipper.ZIP_DEFLATED,
            encryption=pyzipper.WZ_AES,
        ) as zf:
            zf.setpassword(password.encode('utf-8'))
            for f in files:
                arcname = os.path.relpath(f, base_dir)
                zf.write(f, arcname=arcname)
        return True
    except ImportError:
        # 回退：创建普通 zip + 密码注释，并提示用户安装 pyzipper
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                arcname = os.path.relpath(f, base_dir)
                zf.write(f, arcname=arcname)
            zf.comment = f'PASSWORD:{password}'.encode('utf-8')
        return True


def _extract_encrypted_zip(zip_path: str, password: str, output_dir: str) -> bool:
    """解压加密 ZIP。"""
    try:
        import pyzipper
        with pyzipper.AESZipFile(zip_path, 'r') as zf:
            zf.setpassword(password.encode('utf-8'))
            zf.extractall(output_dir)
        return True
    except ImportError:
        import zipfile
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(output_dir, pwd=password.encode('utf-8'))
            return True
        except (RuntimeError, zipfile.BadZipFile):
            return False


# ── 预览生成 ──────────────────────────────────────────

def generate_preview(video_path: str, output_dir: str) -> dict:
    """
    为单个视频生成预览包：
    - 5 张截图 (JPG) 按时长均匀分布
    - 1 个 GIF 动图（视频中部）
    - 打包为加密 ZIP，密码写入文件名

    返回: {'success': bool, 'zip_path': str, 'error': str|None}
    """
    ffmpeg_path = _find_ffmpeg()
    if not ffmpeg_path:
        return {'success': False, 'zip_path': '', 'error': '未找到 ffmpeg，请安装后重试'}

    duration = _get_video_duration(video_path)
    if duration is None or duration <= 0:
        return {'success': False, 'zip_path': '', 'error': '无法获取视频时长'}

    video_name = os.path.basename(video_path)
    video_name_noext = os.path.splitext(video_name)[0]

    temp_dir = tempfile.mkdtemp(prefix='fwt_preview_')

    try:
        # ── 1. 提取截图 ──
        shot_files = []
        for i, pct in enumerate(SCREENSHOT_PCTS):
            t = duration * pct / 100.0
            shot_name = f'{video_name_noext}_{pct:02d}.jpg'
            shot_path = os.path.join(temp_dir, shot_name)
            if _extract_frame(video_path, t, shot_path):
                shot_files.append(shot_path)

        if not shot_files:
            return {'success': False, 'zip_path': '', 'error': '所有截图提取失败'}

        # ── 2. 提取 GIF ──
        gif_path = os.path.join(temp_dir, f'{video_name_noext}.gif')
        gif_ok = _extract_gif(video_path, duration, gif_path)
        if gif_ok:
            shot_files.append(gif_path)

        # ── 3. 打包加密 ZIP ──
        password = _generate_password()
        zip_name = f'（{password}）【预览】{video_name}.zip'
        zip_path = os.path.join(output_dir, zip_name)

        if not _create_encrypted_zip(zip_path, password, shot_files, temp_dir):
            return {'success': False, 'zip_path': '', 'error': '创建 ZIP 失败'}

        return {'success': True, 'zip_path': zip_path, 'error': None}

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ── 预览解压 ──────────────────────────────────────────

def extract_previews(input_path: str) -> dict:
    """
    解压目录或单个预览 ZIP 文件。
    自动识别文件名中的密码，解压到同名文件夹。

    返回统计信息。
    """
    stats = {'extracted': 0, 'failed': 0, 'errors': []}

    # 收集所有预览 zip 文件
    zip_files = []
    if os.path.isfile(input_path):
        zip_files.append(input_path)
    elif os.path.isdir(input_path):
        for root, dirs, files in os.walk(input_path):
            for f in files:
                if f.endswith('.zip'):
                    zip_files.append(os.path.join(root, f))
    else:
        print(f"错误: 路径不存在: {input_path}")
        return stats

    if not zip_files:
        print("未找到预览 ZIP 文件。")
        return stats

    print(f"\n找到 {len(zip_files)} 个 ZIP 文件\n")

    for zip_path in zip_files:
        zip_name = os.path.basename(zip_path)
        match = PREVIEW_ZIP_RE.match(zip_name)

        if not match:
            continue  # 不是预览包，跳过

        password = match.group(1)
        original_name = match.group(2)

        # 解压到同级目录下的子文件夹
        extract_dir = os.path.join(
            os.path.dirname(zip_path),
            f'[预览] {original_name}'
        )
        os.makedirs(extract_dir, exist_ok=True)

        print(f"[解压] {zip_name}")
        if _extract_encrypted_zip(zip_path, password, extract_dir):
            stats['extracted'] += 1
            print(f"       → {extract_dir}")
        else:
            stats['failed'] += 1
            stats['errors'].append((zip_name, '解压失败，请确认已安装 pyzipper'))
            print(f"       → 失败")

    return stats

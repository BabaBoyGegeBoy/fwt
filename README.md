# FWT - File Wash & Transform

视频文件洗码混淆工具，用于安全将隐私视频上传至网盘。

---

## 设计思路

| 防护层 | 手段 | 目的 |
|:--|------|------|
| **MD5 洗码** | 文件末尾追加 5 字节随机数 | 改变文件哈希，防止 MD5/SHA1 封禁 |
| **文件头混淆** | 前 128 字节 XOR 随机密钥 | 破坏视频文件魔数，防止文件头扫描识别 |
| **后缀伪装** | 统一改为 `.fwt` | 防止通过后缀识别为视频 |
| **预览独立** | 截图 + GIF → 加密 ZIP | 不下载视频也能预览内容 |

处理后的文件**完全不可被网盘识别为视频**，可安全上传存储。

---

## 使用流程

```
┌──────────┐     ┌──────────────┐     ┌──────────┐
│ 原始视频  │ ──→ │ FWT 处理     │ ──→ │ 上传网盘  │
│ 目录 A   │     │ → A_washed/  │     │          │
└──────────┘     └──────────────┘     └──────────┘
                                              │
                      ┌───────────────────────┘
                      ▼
                ┌──────────┐     ┌──────────────┐
                │ 下载预览  │ ──→ │ FWT preview  │
                │ ZIP 文件  │     │ 查看截图/GIF  │
                └──────────┘     └──────────────┘

                ┌──────────┐     ┌──────────────┐
                │ 下载 .fwt │ ──→ │ FWT restore  │
                │ 到目录 B  │     │ 原地还原+删除 │
                └──────────┘     └──────────────┘
```

---

## 安装依赖

```bash
pip install pyzipper
```

**ffmpeg**（用于生成截图和GIF）：
- Windows: 下载 [ffmpeg](https://ffmpeg.org/download.html)，将 `bin/` 加入 PATH
- macOS: `brew install ffmpeg`
- Linux: `apt install ffmpeg` / `yum install ffmpeg`

---

## 命令用法

### 1. 处理（process）

```bash
# 默认输出：自动生成 输入目录_washed
python fwt.py process -i D:\Videos

# 指定输出目录（如源盘空间不足，输出到其他磁盘）
python fwt.py process -i C:\Videos -o E:\Videos_washed
```

| 参数 | 必填 | 说明 |
|------|:--:|------|
| `-i, --input` | ✅ | 输入视频目录 |
| `-o, --output` | | 输出目录（默认：`输入目录_washed`） |
| `--no-preview` | | 不生成预览 ZIP（仅洗码+混淆，速度更快） |

**处理逻辑：**
- 扫描目录下所有视频文件
- 混淆文件头 → 追加随机字节 → 后缀改为 `.fwt`
- 生成含截图+GIF的加密预览ZIP
- `.torrent` 文件按目录结构原样复制
- 输出到指定目录或自动生成的 `输入目录_washed/`，保持目录结构

### 2. 预览（preview）

```bash
# 解压单个预览包
python fwt.py preview -i "（AbCd1234）【预览】xxx.mp4.zip"

# 解压目录中所有预览包
python fwt.py preview -i D:\Videos_washed
```

自动读取文件名中的密码解压，内容输出到同级 `[预览] 视频名/` 目录。

### 3. 还原（restore）

```bash
python fwt.py restore -i D:\Downloads\B
```

扫描目录下所有 `.fwt` 文件，原地还原为原始视频（bit-perfect），并删除 `.fwt` 文件。

---

## 文件格式说明

### 处理后 `.fwt` 文件结构

```
┌─────────────────────────────────────┐
│  原始内容（前 128B XOR 混淆）        │
├─────────────────────────────────────┤
│  5 字节随机数（MD5 洗码）            │
├─────────────────────────────────────┤
│  "FWT1" 魔数 (4B)                   │
├─────────────────────────────────────┤
│  JSON 元数据                         │
│  { "v":1, "ext":".mp4",             │
│    "hlen":128, "hkey":"..." }       │
├─────────────────────────────────────┤
│  JSON 长度 (2B, big-endian)  ← 末尾 │
└─────────────────────────────────────┘
```

### 预览 ZIP 文件名格式

```
（随机8位密码）【预览】原始视频名.扩展名.zip
```

示例：`（aB3xQ7kZ）【预览】movie.mp4.zip`
密码：`aB3xQ7kZ`

---

## 实用场景

### 场景一：源盘空间不足 → 跨盘输出

```bash
# C 盘空间不够存放处理后的文件（和源文件同等大小），输出到 E 盘
python fwt.py process -i C:\Users\xxx\Videos -o E:\Videos_washed
```

### 场景二：快速洗码（不生成预览）

```bash
# 纯洗码+混淆，跳过 ffmpeg 截图，适合大文件快速处理
python fwt.py process -i D:\Movies --no-preview
```

### 场景三：仅下载预览，找到目标视频

```bash
# 从网盘下载预览 ZIP 到本地，解压查看
python fwt.py preview -i E:\Downloads\（密码）【预览】xxx.mp4.zip
# 或批量解压整个目录
python fwt.py preview -i E:\Downloads\
```

### 场景四：下载视频后还原

```bash
# 从网盘下载 .fwt 到目录 B，原地还原（.fwt 自动删除）
python fwt.py restore -i E:\Downloads\B
```

### 完整工作流示例

```bash
# 1. 处理 C 盘视频，输出到 E 盘
python fwt.py process -i C:\Users\xxx\Videos -o E:\MyVideos_washed

# 2. 上传 E:\MyVideos_washed 到网盘（整个文件夹）

# 3. 想预览某视频 → 下载对应预览 ZIP → 解压查看
python fwt.py preview -i "（密码）【预览】xxx.mp4.zip"

# 4. 确定要下载 → 下载对应 .fwt 到本地 → 还原
python fwt.py restore -i E:\Downloads\B
```

---

## 支持的视频格式

`.mp4` `.mkv` `.mov` `.avi` `.wmv` `.flv` `.webm` `.ts` `.m4v` `.3gp` `.rmvb` `.rm` `.vob` `.ogv` `.mts` `.m2ts` `.asf` `.divx` `.xvid` `.f4v` `.mpeg` `.mpg` `.mpe` `.m2v` `.dat` `.swf`

---

## 还原说明（手动）

如果工具不可用，也可以手动还原：

1. 用十六进制编辑器打开 `.fwt` 文件
2. 读取文件末尾 2 字节，得到 JSON 长度（big-endian uint16）
3. 从末尾向前读出该长度的 JSON 元数据
4. 继续向前 4 字节验证 `FWT1` 魔数
5. 获取 `hlen`（混淆字节数）和 `hkey`（Base64 密钥）
6. 将文件前 `hlen` 字节与 `hkey` 逐字节 XOR 还原
7. 截去末尾（5字节随机 + 4字节魔数 + JSON + 2字节长度），保留原始大小
8. 重命名为原后缀

---

## 同类项目

本目录下还有两个相关工具：

| 项目 | 功能 |
|------|------|
| `file_wash_tool/` | 轻量级洗码（仅追加5字节改MD5） |
| `file_encryptor/` | AES 全量加密（需客户端解密播放） |

---

## 注意事项

- 处理后文件**不要创建分享链接**，否则可能被人工审查
- ffmpeg 未安装时预览功能不可用，但处理/还原不受影响
- 预览 ZIP 推荐解压查看，在线解压可能触发网盘扫描
- 还原是 **bit-perfect**（100% 还原），与原始文件完全一致

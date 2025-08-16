# 视频合成处理系统

这是一个专业的视频合成处理系统，主要用于处理画中画视频效果和字幕合成。

## 主要功能

1. 视频合成
   - 支持画中画效果
   - 蓝幕抠像
   - 动态缩放效果
   - 字幕合成（支持 SRT 和 ASS 格式）

2. 动态缩放效果详细说明
   系统实现了一个独特的三阶段渐进式放大效果：

   a) 时间周期组成：
   - 初始延迟 (3秒)：保持原始大小
   - 第一级放大：
     * 过渡时间 (2秒)：从 1.0 平滑放大到 1.5
     * 持续时间 (5-8秒随机)：保持 1.5 倍大小
   - 第二级放大：
     * 过渡时间 (2秒)：从 1.5 平滑放大到 1.7
     * 持续时间 (5-8秒随机)：保持 1.7 倍大小
   - 第三级放大：
     * 过渡时间 (2秒)：从 1.7 平滑放大到 1.8
     * 持续时间 (5-8秒随机)：保持 1.8 倍大小
   - 快速收缩 (0.3秒)：从 1.8 快速回到原始大小
   - 正常阶段 (5-8秒随机)：保持原始大小
   - 然后循环重复以上效果

   b) 缓动函数说明：
   - 放大过渡：使用三次方缓入缓出函数 (ease-in-out-cubic)
     * 开始时缓慢加速
     * 中间部分匀速
     * 接近目标值时缓慢减速
   - 快速缩小：使用四次方缓出函数 (ease-out-quart)
     * 开始时快速收缩
     * 结束时平滑过渡

   c) 随机时间说明：
   - 每个放大级别的持续时间随机生成
   - 范围：5-8秒
   - 目的：增加视觉变化，避免机械感
   - 每个循环周期的时间都不同

## 技术特点

1. 缩放效果实现
   - 使用 OpenCV 的 warpAffine 进行精确缩放
   - 支持多级缩放配置
   - 平滑的过渡动画
   - 抖动消除处理

2. 视频处理
   - 支持高质量的视频编码（H.264）
   - 使用 FFmpeg 进行视频合成
   - 支持自定义字体配置
   - 智能边界处理

3. 性能优化
   - 使用 OpenCV 进行高效的图像处理
   - 支持进度显示和日志记录
   - 包含临时文件自动清理机制
   - 错误处理和恢复机制

## 目录结构

```
project/
├── assets/
│   ├── fonts/              # 字体文件
│   ├── main_videos/        # 主视频文件
│   └── pip1_videos/        # 画中画视频和字幕文件
├── outputs/                # 输出目录
├── video_composer.py       # 主程序
├── blue_screen.py         # 蓝幕处理模块
└── srt2ass.py            # 字幕转换模块
```

## 使用方法

1. 准备文件
   - 将主视频放入 `assets/main_videos/` 目录
   - 将画中画视频放入 `assets/pip1_videos/` 目录
   - 将对应的字幕文件（.srt 或 .ass）放入相同目录

2. 运行程序
   ```bash
   python video_composer.py
   ```

3. 输出文件
   - 处理后的视频将保存在 `outputs/{视频名称}/` 目录下
   - 文件名格式：`final_output_YYYYMMDD_HHMMSS.mp4`

## 配置说明

1. 视频处理配置
   ```python
   class VideoConfig:
       def __init__(self):
           self.ffmpeg_path = r"ffmpeg\bin\ffmpeg.exe"
           self.font_path = "assets/fonts/字由玄真.ttf"
           self.output_dir = "outputs"
           self.temp_dir = "temp"
           self.video_quality = 23  # CRF值
           self.preset = "fast"     # 编码预设
   ```

2. 缩放效果配置
   ```python
   class ScaleEffect:
       def __init__(self):
           self.scale_levels = [1.5, 1.7, 1.8]  # 放大级别
           self.transition_time = 2.0   # 过渡时间
           self.shrink_time = 0.3      # 缩小时间
           self.min_hold_time = 5.0    # 最小持续时间
           self.max_hold_time = 8.0    # 最大持续时间
           self.initial_delay = 3.0    # 初始延迟
   ```

## 注意事项

1. 确保系统已安装 FFmpeg 并正确配置路径
2. 视频文件名要与字幕文件名对应
3. 建议使用 ASS 格式字幕，支持更多样式设置
4. 处理大文件时注意磁盘空间充足

## 日志说明

系统会输出详细的处理日志，包括：
- 视频信息（尺寸、帧率、时长等）
- 处理进度
- 缩放效果配置
- 错误信息（如果有）
- 处理完成统计

## 错误处理

系统包含完善的错误处理机制：
- 文件不存在检查
- 视频格式验证
- 临时文件清理
- 处理失败恢复

## 项目说明
这是一个视频合成处理工具，支持画中画效果和字幕添加。

## 功能特点
- 支持画中画视频合成
- 支持字幕添加（SRT和ASS格式）
- 支持视频缩放效果
- 支持自定义字体和样式

## 字幕配置说明

### 1. 基本配置
```python
# 播放区域设置
PLAY_RES_X = 720    # 播放区域宽度（竖屏视频）
PLAY_RES_Y = 1280   # 播放区域高度（竖屏视频）

# 字体配置
FONT_PATH = "assets/fonts/国潮手书.ttf"
CHINESE_FONT = "国潮手书"
ENGLISH_FONT = "Arial"

# 字体大小
CHINESE_FONT_SIZE = 45   # 中文字体大小
ENGLISH_FONT_SIZE = 30   # 英文字体大小
```

### 2. 字幕样式定义
系统提供两种预设样式：

#### 中文样式（Chinese）：
```
字体：国潮手书
字号：45
主色：白色 (&H00FFFFFF)
描边：黑色 (&H00000000)
背景：黑色 (&H00000000)
粗体：是
描边宽度：1.5
对齐：2（底部居中）
边距：左右10，垂直400
编码：1
```

#### 英文样式（English）：
```
字体：Arial
字号：30
主色：黄色 (&H0000FFFF)
描边：黑色 (&H00000000)
背景：黑色 (&H00000000)
粗体：否
描边宽度：1.5
对齐：2（底部居中）
边距：左右10，垂直365
编码：1
```

### 3. 字幕垂直位置说明
字幕的垂直位置由两个参数共同决定：
1. Alignment（对齐方式）：
   - 1-3：底部对齐
   - 4-6：中部对齐
   - 7-9：顶部对齐

2. MarginV（垂直边距）：
   - 中文字幕：400像素（距离底边400像素）
   - 英文字幕：365像素（距离底边365像素）

### 4. 配置文件说明
字幕样式配置统一由 `subtitle_styles.py` 管理，包括：
- 播放区域设置
- 字体配置
- 字体大小
- 样式定义
- ASS文件结构

## 字幕样式配置

### 1. 基本配置
```python
# 播放区域设置
PLAY_RES_X = 720    # 播放区域宽度
PLAY_RES_Y = 1280   # 播放区域高度

# 字体配置
FONT_PATH = "assets/fonts/国潮手书.ttf"
CHINESE_FONT = "国潮手书"
ENGLISH_FONT = "Arial"

# 字体大小
CHINESE_FONT_SIZE = 45   # 中文字体大小
ENGLISH_FONT_SIZE = 30   # 英文字体大小
```

### 2. 字幕样式定义
系统提供两种预设样式：

#### 中文样式（Chinese）：
```
字体：国潮手书
字号：45
主色：白色 (&H00FFFFFF)
描边：黑色 (&H00000000)
背景：黑色 (&H00000000)
粗体：是
描边宽度：1.5
对齐：2（底部居中）
边距：左右10，垂直400
编码：1
```

#### 英文样式（English）：
```
字体：Arial
字号：30
主色：黄色 (&H0000FFFF)
描边：黑色 (&H00000000)
背景：黑色 (&H00000000)
粗体：否
描边宽度：1.5
对齐：2（底部居中）
边距：左右10，垂直365
编码：1
```

### 3. ASS文件结构
```
[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
```

### 4. 更新说明
- 移除了旧的assHeaders.txt配置
- 统一使用subtitle_styles.py进行字幕样式管理
- 优化了中英文字幕的显示效果
- 调整了播放区域分辨率以适应竖屏视频

## 使用说明

### 1. 环境要求
- Python 3.6+
- FFmpeg
- 相关字体文件

### 2. 安装步骤
1. 克隆项目到本地
2. 安装依赖包
3. 配置FFmpeg路径
4. 准备字体文件

### 3. 配置文件
可以通过修改 `config.py` 中的 `SUBTITLE_STYLES` 来自定义字幕样式。

### 4. 使用方法
1. 准备视频文件
2. 准备字幕文件（支持.srt或.ass格式）
3. 运行程序进行处理

## 注意事项
1. 确保系统已安装 FFmpeg 并正确配置路径
2. 视频文件名要与字幕文件名对应
3. 建议使用 ASS 格式字幕，支持更多样式设置
4. 处理大文件时注意磁盘空间充足

## 日志说明
系统会输出详细的处理日志，包括：
- 视频信息（尺寸、帧率、时长等）
- 处理进度
- 缩放效果配置
- 错误信息（如果有）
- 处理完成统计

## 错误处理
系统包含完善的错误处理机制：
- 文件不存在检查
- 视频格式验证
- 临时文件清理
- 处理失败恢复 
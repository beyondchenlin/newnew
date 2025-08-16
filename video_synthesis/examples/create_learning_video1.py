"""
创建学习视频模块：将analysis.json中的词汇学习信息叠加到视频上
使用方法：python create_learning_video.py
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import random
import cv2
import numpy as np
import subprocess
import math
import traceback
import re

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(current_dir)

from video_synthesis.core.video_processor import get_output_filename
from video_synthesis.utils.ffmpeg_utils import get_video_duration, run_ffmpeg_command
from video_synthesis.config.settings import VIDEO_SETTINGS

# 配置日志
def setup_logging():
    """配置详细的日志记录"""
    # 创建logs目录
    os.makedirs("logs", exist_ok=True)
    
    # 生成日志文件名
    log_filename = f'logs/create_learning_video_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    # 配置根日志记录器
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # 文件处理器 - 记录所有级别的日志
            logging.FileHandler(log_filename, encoding='utf-8'),
            # 控制台处理器 - 只显示INFO及以上级别的日志
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # 创建logger实例
    logger = logging.getLogger('create_learning_video')
    
    # 记录系统信息
    logger.info("="*50)
    logger.info("程序启动")
    logger.info(f"当前工作目录: {os.getcwd()}")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"OpenCV版本: {cv2.__version__}")
    logger.info(f"日志文件: {log_filename}")
    
    # 记录关键目录信息
    dirs_to_check = [
        "assets/pip1_videos",
        "assets/pip2_videos",
        "assets/pip3_videos",
        "fonts",
        "temp",
        "logs"
    ]
    
    logger.info("\n检查关键目录:")
    for dir_path in dirs_to_check:
        if os.path.exists(dir_path):
            files = os.listdir(dir_path)
            logger.info(f"{dir_path}: 存在 ({len(files)} 个文件)")
            for file in files:
                file_path = os.path.join(dir_path, file)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    logger.info(f"  - {file} ({size/1024/1024:.2f} MB)")
        else:
            logger.warning(f"{dir_path}: 不存在")
    
    return logger

# 创建logger实例
logger = setup_logging()

# 在文件开头添加配置
USE_SAME_FILENAME = True  # True: 使用相同文件名, False: 添加_learning后缀

def find_latest_analysis_dir(base_dir: str = "subtitles") -> Optional[str]:
    """
    查找最新的分析目录
    
    Args:
        base_dir: 基础目录路径
        
    Returns:
        str: 最新分析目录的路径，如果未找到则返回None
    """
    logger.info(f"开始查找最新分析目录，基础目录: {base_dir}")
    
    if not os.path.exists(base_dir):
        logger.error(f"基础目录不存在: {base_dir}")
        print(f"❌ 基础目录不存在: {base_dir}")
        return None
        
    # 列出所有视频文件夹
    video_folders = []
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path):
            logger.info(f"找到视频文件夹: {item}")
            video_folders.append(item_path)
    
    if not video_folders:
        logger.error(f"未找到任何视频文件夹在: {base_dir}")
        print(f"❌ 未找到任何视频文件夹在: {base_dir}")
        return None
    
    # 获取最新的视频文件夹
    latest_video_folder = max(video_folders, key=os.path.getmtime)
    logger.info(f"最新的视频文件夹: {latest_video_folder}")
    
    # 查找序号目录
    sequence_dirs = []
    for item in os.listdir(latest_video_folder):
        if item.isdigit() and len(item) == 4:
            sequence_path = os.path.join(latest_video_folder, item)
            if os.path.isdir(sequence_path):
                logger.info(f"找到序号目录: {item}")
                sequence_dirs.append(sequence_path)
    
    if not sequence_dirs:
        logger.error(f"未找到序号目录在: {latest_video_folder}")
        print(f"❌ 未找到序号目录在: {latest_video_folder}")
        return None
    
    # 获取最新的序号目录
    latest_sequence_dir = max(sequence_dirs, key=os.path.getmtime)
    logger.info(f"最新的序号目录: {latest_sequence_dir}")
    
    # 查找分析目录
    analysis_dirs = []
    for item in os.listdir(latest_sequence_dir):
        if item.startswith("subtitle_"):
            analysis_path = os.path.join(latest_sequence_dir, item)
            if os.path.isdir(analysis_path):
                logger.info(f"找到分析目录: {item}")
                analysis_dirs.append(analysis_path)
    
    if not analysis_dirs:
        logger.error(f"未找到分析文件目录在: {latest_sequence_dir}")
        print(f"❌ 未找到分析文件目录")
        return None
    
    # 获取最新的分析目录
    latest_analysis_dir = max(analysis_dirs, key=os.path.getmtime)
    logger.info(f"最新的分析目录: {latest_analysis_dir}")
    
    # 检查分析文件是否存在
    analysis_file = os.path.join(latest_analysis_dir, "analysis.json")
    if not os.path.exists(analysis_file):
        logger.error(f"分析文件不存在: {analysis_file}")
        print(f"❌ 分析文件不存在: {analysis_file}")
        return None
        
    logger.info(f"找到有效的分析目录: {latest_analysis_dir}")
    return latest_analysis_dir

def create_text_image(text: str, font_size: int, color: str, image_width: int = 720, image_height: int = 1280, y_offset: float = 0.5) -> str:
    """创建文字图片
    Args:
        text: 要渲染的文字
        font_size: 字体大小
        color: 文字颜色 (RGB格式，如 "#FFFFFF")
        image_width: 图片宽度 (默认720，竖屏)
        image_height: 图片高度 (默认1280，竖屏)
        y_offset: 垂直偏移比例 (0-1)
    Returns:
        str: 生成的图片路径
    """
    logger.debug(f"创建文字图片: text='{text}', font_size={font_size}, color='{color}'")
    # 创建透明背景的图片
    image = Image.new('RGBA', (image_width, image_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    font_path = os.path.abspath(os.path.join("fonts", "方正粗黑宋简体.ttf"))
    font = ImageFont.truetype(font_path, font_size)
    
    # 获取文字大小
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # 计算位置（水平居中，垂直位置由y_offset控制）
    x = (image_width - text_width) // 2
    y = int(image_height * y_offset - text_height / 2)
    
    # 绘制文字阴影和边框
    shadow_color = (0, 0, 0, 128)  # 半透明黑色阴影
    border_color = (0, 0, 0, 255)  # 不透明黑色边框
    
    # 绘制阴影
    for dx, dy in [(2, 2)]:
        draw.text((x + dx, y + dy), text, font=font, fill=shadow_color)
    
    # 绘制边框
    for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
        draw.text((x + dx, y + dy), text, font=font, fill=border_color)
    
    # 绘制主文字
    draw.text((x, y), text, font=font, fill=color)
    
    # 保存图片
    os.makedirs("temp", exist_ok=True)
    output_path = os.path.join("temp", f"{hash(text)}.png")
    image.save(output_path)
    
    return output_path

def get_clip_path(base_dir: str, item_type: str, text: str) -> Tuple[str, str]:
    """获取视频片段路径
    Args:
        base_dir: 基础目录
        item_type: 项目类型 (vocabulary/phrases/expressions)
        text: 文本内容
    Returns:
        Tuple[str, str]: (输入视频路径, 输出视频路径)
    """
    logger.debug(f"开始获取视频路径:")
    logger.debug(f"基础目录: {base_dir}")
    logger.debug(f"项目类型: {item_type}")
    logger.debug(f"原始文本: {text}")
    
    # 获取原始视频目录
    clip_dir = os.path.join(base_dir, "clips", item_type)
    logger.debug(f"视频目录: {clip_dir}")
    
    # 规范化文本，用于文件名匹配
    text_normalized = text.replace(" ", "_")
    text_normalized = re.sub(r'[^\w\-_]', '', text_normalized)
    text_normalized = text_normalized.lower()
    logger.debug(f"规范化后的文本: {text_normalized}")
    
    # 在对应目录中查找视频文件
    target_dir = os.path.join(clip_dir, text_normalized)
    logger.debug(f"目标目录: {target_dir}")
    
    if os.path.exists(target_dir):
        logger.debug(f"目标目录存在，查找视频文件...")
        for file in os.listdir(target_dir):
            logger.debug(f"检查文件: {file}")
            # 优先查找enzh版本
            if file.endswith("_enzh.mp4"):
                input_video = os.path.join(target_dir, file)
                if USE_SAME_FILENAME:
                    output_video = input_video
                else:
                    output_video = os.path.join(target_dir, file.replace("_enzh.mp4", "_learning.mp4"))
                logger.debug(f"找到enzh版本视频:")
                logger.debug(f"输入视频: {input_video}")
                logger.debug(f"输出视频: {output_video}")
                return input_video, output_video
            # 如果没有enzh版本，则使用complete版本
            elif file.endswith("_complete.mp4"):
                input_video = os.path.join(target_dir, file)
                if USE_SAME_FILENAME:
                    output_video = input_video
                else:
                    output_video = os.path.join(target_dir, file.replace("_complete.mp4", "_learning.mp4"))
                logger.debug(f"找到complete版本视频:")
                logger.debug(f"输入视频: {input_video}")
                logger.debug(f"输出视频: {output_video}")
                return input_video, output_video
    
    # 如果没找到视频，使用默认路径
    logger.debug("未找到现有视频，使用默认路径")
    os.makedirs(target_dir, exist_ok=True)
    input_video = os.path.join(target_dir, f"{text_normalized}_enzh.mp4")  # 默认使用enzh版本
    if USE_SAME_FILENAME:
        output_video = input_video
    else:
        output_video = os.path.join(target_dir, f"{text_normalized}_learning.mp4")
    
    logger.debug(f"默认路径:")
    logger.debug(f"输入视频: {input_video}")
    logger.debug(f"输出视频: {output_video}")
    
    return input_video, output_video

def create_cover_image(text: str, chinese: str, notes: str, image_width: int = 720, image_height: int = 1280) -> str:
    """创建文字封面图片
    Args:
        text: 英文文本
        chinese: 中文翻译
        notes: 注释说明
        image_width: 图片宽度
        image_height: 图片高度
    Returns:
        str: 生成的图片路径
    """
    logger.debug(f"创建封面图片: text='{text}', chinese='{chinese}', notes='{notes}'")
    # 创建透明背景的图片
    image = Image.new('RGBA', (image_width, image_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    font_path = os.path.abspath(os.path.join("fonts", "方正粗黑宋简体.ttf"))
    
    # 动态计算英文字体大小
    margin = 100  # 两边边距
    max_font_size = 80  # 最大字体大小
    min_font_size = 30  # 最小字体大小
    available_width = image_width - 2 * margin  # 可用宽度
    
    # 二分查找合适的字体大小
    font_size = max_font_size
    while font_size >= min_font_size:
        font_english = ImageFont.truetype(font_path, font_size)
        bbox = draw.textbbox((0, 0), text, font=font_english)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= available_width:
            break
        font_size -= 2  # 每次减小2个像素尝试
    
    # 如果找不到合适的大小，使用最小字体
    if font_size < min_font_size:
        font_size = min_font_size
        font_english = ImageFont.truetype(font_path, font_size)
        bbox = draw.textbbox((0, 0), text, font=font_english)
        text_width = bbox[2] - bbox[0]
    
    # 计算英文文本位置
    x = (image_width - text_width) // 2
    y = image_height * 0.3 - 100  # 向上移动100像素
    
    # 绘制英文文本的边框和阴影
    for dx, dy in [(2, 2)]:  # 阴影
        draw.text((x + dx, y + dy), text, font=font_english, fill=(0, 0, 0, 180))
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:  # 边框
        draw.text((x + dx, y + dy), text, font=font_english, fill=(255, 255, 255, 180))
    draw.text((x, y), text, font=font_english, fill=(255, 255, 255, 255))
    
    # 中文翻译 (中号黄色)
    font_chinese = ImageFont.truetype(font_path, 80)
    bbox = draw.textbbox((0, 0), chinese, font=font_chinese)
    text_width = bbox[2] - bbox[0]
    x = (image_width - text_width) // 2
    y = image_height * 0.5 - 100  # 向上移动100像素
    # 绘制边框和阴影
    for dx, dy in [(2, 2)]:
        draw.text((x + dx, y + dy), chinese, font=font_chinese, fill=(0, 0, 0, 180))
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        draw.text((x + dx, y + dy), chinese, font=font_chinese, fill=(255, 255, 255, 180))
    draw.text((x, y), chinese, font=font_chinese, fill=(255, 255, 0, 255))
    
    # 注释说明 (小号青色，自动换行)
    font_notes = ImageFont.truetype(font_path, 30)
    margin = 100  # 左右边距
    max_width = image_width - 2 * margin
    y = image_height * 0.7 - 100  # 向上移动100像素
    line_height = 50  # 行高
    
    # 计算所有行的宽度，找出最宽的一行
    lines = []
    max_line_width = 0
    
    # 文本换行处理
    words = notes
    remaining = words
    
    while remaining:
        # 计算当前行可以容纳的文字
        for i in range(len(remaining)):
            test_text = remaining[:i+1]
            bbox = draw.textbbox((0, 0), test_text, font=font_notes)
            if bbox[2] - bbox[0] > max_width:
                if i > 0:
                    # 找到合适的断句点
                    break_points = ['，', '。', '；', '：', '、', ' ']
                    break_index = -1
                    for point in break_points:
                        pos = remaining[:i].rfind(point)
                        if pos > break_index:
                            break_index = pos
                    if break_index == -1:
                        break_index = i - 1
                    current_line = remaining[:break_index + 1]
                    remaining = remaining[break_index + 1:].lstrip()
                else:
                    current_line = remaining[0]
                    remaining = remaining[1:]
                break
        else:
            current_line = remaining
            remaining = ''
        
        # 计算当前行宽度并保存
        bbox = draw.textbbox((0, 0), current_line, font=font_notes)
        line_width = bbox[2] - bbox[0]
        max_line_width = max(max_line_width, line_width)
        lines.append(current_line)
    
    # 计算整个文本块的起始x坐标（居中）
    text_block_x = (image_width - max_line_width) // 2
    
    # 绘制每一行文本
    for line in lines:
        # 绘制黑色描边（四个方向）
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            draw.text((text_block_x + dx, y + dy), line, font=font_notes, fill=(0, 0, 0, 255))
        
        # 绘制主文本（左对齐）
        draw.text((text_block_x, y), line, font=font_notes, fill=(0, 255, 75, 255))
        
        y += line_height
    
    # 保存图片
    os.makedirs("temp", exist_ok=True)
    output_path = os.path.join("temp", f"cover_{hash(text)}.png")
    image.save(output_path)
    
    return output_path

def get_random_greenscreen_video() -> str:
    """获取随机的绿幕视频
    Returns:
        str: 绿幕视频路径
    """
    green_screen_dir = "assets/pip3_videos"
    if not os.path.exists(green_screen_dir):
        logger.error(f"绿幕视频目录不存在: {green_screen_dir}")
        return None
        
    videos = [f for f in os.listdir(green_screen_dir) if f.endswith(('.mp4', '.mov'))]
    if not videos:
        logger.error(f"未找到绿幕视频")
        return None
        
    selected_video = os.path.join(green_screen_dir, random.choice(videos))
    logger.info(f"选择的绿幕视频: {selected_video}")
    return selected_video

def sample_green_color(input_video: str) -> Optional[str]:
    """采样绿幕视频的颜色，从四个边缘采样"""
    logger.info("="*50)
    logger.info("开始采样绿幕颜色")
    logger.info(f"输入视频: {input_video}")
    
    try:
        # 创建临时目录
        os.makedirs("temp", exist_ok=True)
        frame_path = os.path.join("temp", f"sample_frame_{hash(input_video)}.png")
        
        # 提取视频第一帧
        ffmpeg_cmd = [
            "ffmpeg",
            "-i", input_video,
            "-vframes", "1",  # 只提取一帧
            "-y",
            frame_path
        ]
        
        logger.info("提取视频第一帧")
        logger.info(f"命令: {' '.join(ffmpeg_cmd)}")
        run_ffmpeg_command(ffmpeg_cmd)
        
        if not os.path.exists(frame_path):
            logger.error("提取视频帧失败")
            return None
            
        logger.info(f"成功提取第一帧: {frame_path}")
            
        # 使用PIL读取图片并采样边缘的颜色
        with Image.open(frame_path) as img:
            width, height = img.size
            logger.info(f"图片尺寸: {width}x{height}")
            
            # 采样点的位置（距离边缘10个像素）
            sample_points = [
                # 左边缘中点
                (10, height//2),
                # 右边缘中点
                (width-10, height//2),
                # 上边缘中点
                (width//2, 10),
                # 下边缘中点
                (width//2, height-10)
            ]
            
            # 收集所有采样点的颜色
            colors = []
            logger.info("采样点颜色:")
            for i, (x, y) in enumerate(sample_points):
                color = img.getpixel((x, y))
                # 如果是RGBA格式，只取RGB部分
                if len(color) > 3:
                    logger.info(f"点 {i+1} 原始颜色(RGBA): {color}")
                    color = color[:3]
                logger.info(f"点 {i+1} ({x}, {y}): RGB{color}")
                colors.append(color)
            
            # 计算平均颜色
            avg_color = [
                sum(c[0] for c in colors) // len(colors),  # R
                sum(c[1] for c in colors) // len(colors),  # G
                sum(c[2] for c in colors) // len(colors)   # B
            ]
            
            # 转换为十六进制格式
            hex_color = '0x{:02x}{:02x}{:02x}'.format(*avg_color)
            logger.info(f"平均颜色: RGB{avg_color}")
            logger.info(f"十六进制颜色: {hex_color}")
            
            # 清理临时文件
            os.remove(frame_path)
            logger.info("清理临时文件完成")
            
            return hex_color
            
    except Exception as e:
        logger.exception("采样绿幕颜色时出错")
        return None

def process_greenscreen_video(input_video: str, output_video: str):
    """处理绿幕视频

    Args:
        input_video (str): 输入视频路径
        output_video (str): 输出视频路径
    """
    # 采样绿幕颜色
    cap = cv2.VideoCapture(input_video)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        logger.error("无法读取视频帧")
        return False
        
    # 转换为RGB颜色空间
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # 获取图像尺寸
    height, width = frame_rgb.shape[:2]
    
    # 只采样边缘的点（距离边缘20像素）
    margin = 20
    sample_points = [
        (margin, height//2),           # 左侧中点
        (width-margin, height//2),     # 右侧中点
        (width//2, margin),            # 上方中点
        (width//2, height-margin)      # 下方中点
    ]
    
    colors = []
    for x, y in sample_points:
        color = frame_rgb[y, x]
        colors.append(color)
        logger.info(f"采样点 ({x}, {y}): RGB={color}")
    
    # 计算平均颜色
    avg_color = np.mean(colors, axis=0).astype(int)
    logger.info(f"平均颜色: RGB={avg_color}")
    
    # 转换为十六进制格式
    green_color = f"0x{avg_color[0]:02x}{avg_color[1]:02x}{avg_color[2]:02x}"
    logger.info(f"绿幕颜色: {green_color}")

    # 使用测试验证过的最佳参数
    filter_complex = f"[0:v]format=yuv444p,colorkey={green_color}:0.1:0.1[fg]"
    
    # 构建FFmpeg命令
    cmd = [
        "ffmpeg",
        "-i", input_video,
        "-filter_complex", filter_complex,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-y",
        output_video
    ]
    
    # 执行命令
    logger.info(f"执行命令: {' '.join(cmd)}")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    
    if stdout:
        logger.info(f"输出: {stdout.decode('utf-8', errors='ignore')}")
    if stderr:
        logger.info(f"错误: {stderr.decode('utf-8', errors='ignore')}")
    
    success = process.returncode == 0
    if success:
        logger.info(f"✅ 绿幕处理成功: {output_video}")
    else:
        logger.error(f"❌ 绿幕处理失败: {output_video}")
    
    return success

def process_clip(input_video: str, output_video: str, item: Dict) -> bool:
    """处理单个视频片段"""
    logger.info("="*80)
    logger.info("开始处理视频片段")
    logger.info(f"输入视频: {input_video}")
    logger.info(f"输出视频: {output_video}")
    logger.info(f"处理项目: {json.dumps(item, ensure_ascii=False, indent=2)}")
    
    # 检查输入参数
    if not input_video or not output_video:
        logger.error("输入或输出视频路径为空")
        return False
        
    if not item:
        logger.error("处理项目为空")
        return False
        
    # 检查必要的字段
    required_fields = ['text', 'chinese']
    for field in required_fields:
        if field not in item:
            logger.error(f"处理项目缺少必要字段: {field}")
            return False
    
    # 记录视频文件信息
    if os.path.exists(input_video):
        file_size = os.path.getsize(input_video)
        logger.info(f"输入视频大小: {file_size/1024/1024:.2f} MB")
    else:
        logger.error(f"视频文件不存在: {input_video}")
        return False
    
    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(output_video)
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"确保输出目录存在: {output_dir}")
        
        # 如果输入和输出路径相同，创建备份
        if input_video == output_video:
            backup_video = input_video + ".backup"
            if not os.path.exists(backup_video):
                import shutil
                shutil.copy2(input_video, backup_video)
                logger.info(f"已创建原始文件备份: {backup_video}")
                logger.info(f"备份文件大小: {os.path.getsize(backup_video)/1024/1024:.2f} MB")
        
        # 获取主视频时长
        main_video_path = input_video if input_video != output_video else backup_video
        main_duration = get_video_duration(main_video_path)
        if not main_duration:
            logger.error("无法获取主视频时长")
            return False
        
        logger.info(f"主视频时长: {main_duration}秒")
        
        # 从item中获取文本内容
        text = item["text"]
        chinese = item["chinese"]
        notes = item.get("notes", "")  # notes现在是可选的
        
        logger.info("文本内容:")
        logger.info(f"英文: {text}")
        logger.info(f"中文: {chinese}")
        if notes:
            logger.info(f"注释: {notes}")
        
        # 生成封面图片
        logger.info("开始生成封面图片...")
        cover_img = create_cover_image(text, chinese, notes)
        if not cover_img or not os.path.exists(cover_img):
            logger.error("生成封面图片失败")
            return False
        logger.info(f"封面图片已生成: {cover_img}")
        logger.info(f"封面图片大小: {os.path.getsize(cover_img)/1024:.2f} KB")
        
        # 生成顶部文字图片
        top_text = "看视频学英语："
        logger.info("开始生成顶部文字图片...")
        top_text_img = create_text_image(
            text=top_text,
            font_size=50,
            color="#00FF00",
            y_offset=0.04
        )
        if not top_text_img or not os.path.exists(top_text_img):
            logger.error("生成顶部文字图片失败")
            return False
        logger.info(f"顶部文字图片已生成: {top_text_img}")
        logger.info(f"顶部文字图片大小: {os.path.getsize(top_text_img)/1024:.2f} KB")
        
        # 获取并预处理绿幕视频
        logger.info("开始获取绿幕视频...")
        green_screen_video = get_random_greenscreen_video()
        if not green_screen_video:
            logger.error("未找到绿幕视频")
            return False
        
        logger.info(f"选择的绿幕视频: {green_screen_video}")
        logger.info(f"绿幕视频大小: {os.path.getsize(green_screen_video)/1024/1024:.2f} MB")
        
        # 获取绿幕视频时长
        green_screen_duration = get_video_duration(green_screen_video)
        if not green_screen_duration:
            logger.error("无法获取绿幕视频时长")
            return False
        
        # 计算需要循环的次数（向上取整）
        loop_count = math.ceil(main_duration / green_screen_duration)
        logger.info(f"主视频时长: {main_duration}秒")
        logger.info(f"绿幕视频时长: {green_screen_duration}秒")
        logger.info(f"需要循环次数: {loop_count}")
        
        # 构建FFmpeg命令的filter_complex
        filter_complex = [
            # 处理背景视频 - 确保帧率一致
            "[0:v]format=yuv420p,fps=30[bg]",
            
            # 叠加顶部文字
            "[bg][1:v]overlay=x=W-w-100:y=50[with_top]",
            
            # 叠加封面图片
            "[with_top][2:v]overlay=x=(W-w)/2:y=0[with_cover]",
            
            # 处理绿幕视频
            "[3:v]format=yuv444p,fps=30[fmt]",
            "[fmt]colorkey=0x00FF00:0.3:0.2[keyed]",
            "[keyed]scale=iw*0.3:-1[scaled]",
            
            # 改进的循环处理方式
            f"[scaled]loop=loop={loop_count}:size={int(green_screen_duration*30)}:start=0[looped]",
            
            # 时长控制
            f"[looped]trim=0:{main_duration},setpts=PTS-STARTPTS[timed]",
            
            # 叠加到背景视频
            "[with_cover][timed]overlay=x=W-w-10:y=H-h+10:shortest=1[out]"
        ]
        
        logger.info("FFmpeg filter_complex:")
        for i, filter_line in enumerate(filter_complex, 1):
            logger.info(f"{i}. {filter_line}")
        
        # 构建完整的FFmpeg命令
        ffmpeg_cmd = [
            "ffmpeg",
            "-i", input_video if input_video != output_video else backup_video,  # 主视频
            "-i", top_text_img,    # 顶部文字
            "-i", cover_img,       # 封面图片
            "-i", green_screen_video,  # 绿幕视频
            "-filter_complex", ";".join(filter_complex),
            "-map", "[out]",
            "-map", "0:a?",        # 保留原视频的音频
            "-c:v", "libx264",
            "-preset", "ultrafast",  # 使用更快的编码预设
            "-crf", "23",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            "-y",
            output_video
        ]
        
        logger.info("执行FFmpeg命令:")
        logger.info(" ".join(ffmpeg_cmd))
        
        # 执行命令
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # 实时记录FFmpeg输出
        while True:
            output = process.stderr.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                logger.debug(output.strip())
        
        # 获取命令执行结果
        stdout, stderr = process.communicate()
        
        # 记录完整的输出
        if stdout:
            logger.debug("FFmpeg stdout:")
            logger.debug(stdout)
        if stderr:
            logger.debug("FFmpeg stderr:")
            logger.debug(stderr)
        
        success = process.returncode == 0
        if success:
            if os.path.exists(output_video):
                output_size = os.path.getsize(output_video)
                logger.info(f"✅ 成功生成视频: {output_video}")
                logger.info(f"输出视频大小: {output_size/1024/1024:.2f} MB")
                return True
            else:
                logger.error(f"❌ 输出文件不存在: {output_video}")
                return False
        else:
            logger.error(f"❌ FFmpeg命令执行失败，返回码: {process.returncode}")
            return False
            
    except Exception as e:
        logger.error("处理视频时出错:")
        logger.error(traceback.format_exc())
        return False
    finally:
        # 清理临时文件
        try:
            if 'cover_img' in locals() and os.path.exists(cover_img):
                os.remove(cover_img)
            if 'top_text_img' in locals() and os.path.exists(top_text_img):
                os.remove(top_text_img)
            logger.info("清理临时文件完成")
        except Exception as e:
            logger.warning(f"清理临时文件时出错: {str(e)}")
        logger.info("="*80)

def process_learning_videos(analysis_json_path: str) -> List[str]:
    """处理所有学习视频生成
    Args:
        analysis_json_path: analysis.json文件路径
    Returns:
        List[str]: 成功生成的视频列表
    """
    print("\n=== 开始生成学习视频 ===")
    
    # 1. 检查输入文件
    if not os.path.exists(analysis_json_path):
        print(f"❌ 分析文件不存在: {analysis_json_path}")
        return []
    
    # 2. 读取分析文件
    try:
        with open(analysis_json_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
            print("✅ 成功读取分析文件")
    except Exception as e:
        print(f"❌ 读取分析文件失败: {str(e)}")
        return []
    
    # 获取基础目录
    base_dir = os.path.dirname(analysis_json_path)
    successful_videos = []
    
    def add_successful_video(video_path: str):
        """添加成功生成的视频到列表中，避免重复"""
        if video_path not in successful_videos:
            successful_videos.append(video_path)
    
    # 3. 处理词汇视频
    print("\n--- 处理词汇视频 ---")
    for item in analysis_data.get("vocabulary", []):
        input_video, output_video = get_clip_path(base_dir, "vocabulary", item["text"])
        if process_clip(input_video, output_video, item):
            add_successful_video(output_video)
    
    # 4. 处理短语视频
    print("\n--- 处理短语视频 ---")
    for item in analysis_data.get("phrases", []):
        input_video, output_video = get_clip_path(base_dir, "phrases", item["text"])
        if process_clip(input_video, output_video, item):
            add_successful_video(output_video)
    
    # 5. 处理表达式视频
    print("\n--- 处理表达式视频 ---")
    for item in analysis_data.get("expressions", []):
        input_video, output_video = get_clip_path(base_dir, "expressions", item["text"])
        if process_clip(input_video, output_video, item):
            add_successful_video(output_video)
    
    print(f"\n=== 处理完成 ===")
    print(f"总计成功: {len(successful_videos)} 个视频")
    return successful_videos

def main():
    """主函数"""
    try:
        logger.info("="*80)
        logger.info("开始处理学习视频")
        logger.info(f"当前工作目录: {os.getcwd()}")
        
        # 查找最新的分析目录
        analysis_dir = find_latest_analysis_dir()
        if not analysis_dir:
            logger.error("未找到有效的分析目录")
            return
        
        logger.info(f"找到分析目录: {analysis_dir}")
        
        # 读取分析文件
        analysis_file = os.path.join(analysis_dir, "analysis.json")
        logger.info(f"读取分析文件: {analysis_file}")
        
        try:
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
                logger.debug(f"分析数据: {json.dumps(analysis_data, ensure_ascii=False, indent=2)}")
        except Exception as e:
            logger.error(f"读取分析文件失败: {str(e)}")
            logger.error(traceback.format_exc())
            return
        
        # 处理每种类型的视频
        for item_type in ['vocabulary', 'phrases', 'expressions']:
            if item_type in analysis_data:
                logger.info(f"\n处理 {item_type} 类型的视频")
                logger.info(f"共有 {len(analysis_data[item_type])} 个项目待处理")
                
                for i, item in enumerate(analysis_data[item_type], 1):
                    text = item['text']
                    logger.info(f"\n处理第 {i} 个项目: {text}")
                    
                    # 获取视频路径
                    input_video, output_video = get_clip_path(analysis_dir, item_type, text)
                    logger.info(f"输入视频: {input_video}")
                    logger.info(f"输出视频: {output_video}")
                    
                    # 处理视频
                    if process_clip(input_video, output_video, item):
                        logger.info(f"✅ 成功处理: {text}")
                    else:
                        logger.error(f"❌ 处理失败: {text}")
                        
        logger.info("="*80)
        logger.info("处理完成")
        
    except Exception as e:
        logger.error("程序执行出错:")
        logger.error(traceback.format_exc())
    finally:
        logger.info("程序退出")
        logger.info("="*80)

if __name__ == "__main__":
    main() 
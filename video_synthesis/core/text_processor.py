"""
文字处理相关的函数模块
"""
import os
from PIL import Image, ImageDraw, ImageFont
from video_synthesis.config.settings import TEXT_SETTINGS, FONT_OPTIONS

def calculate_font_size(text: str, base_size: int, max_width: int, font_path: str) -> int:
    """计算适合的字体大小
    Args:
        text: 要显示的文字
        base_size: 基准字体大小
        max_width: 最大可用宽度
        font_path: 字体文件路径
    Returns:
        int: 计算后的字体大小
    """
    min_size = 40
    max_size = base_size
    
    temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    
    font = ImageFont.truetype(font_path, base_size)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    
    if text_width <= max_width:
        return base_size
    
    ratio = max_width / text_width
    size = int(base_size * ratio)
    return max(min_size, min(size, max_size))

def get_font_path():
    """获取可用的字体文件路径
    Returns:
        str: 字体文件路径
    """
    for path, name in FONT_OPTIONS:
        if os.path.exists(path):
            print(f"使用字体: {name}")
            return path
    raise Exception("未找到可用的字体文件")

def create_text_overlay(title1: str, title2: str, bottom_text: str, width: int, height: int) -> str:
    """创建文字叠加图片
    Args:
        title1: 顶部主标题
        title2: 顶部副标题
        bottom_text: 底部文字
        width: 图片宽度
        height: 图片高度
    Returns:
        str: 生成的图片路径
    """
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 获取字体文件
    font_path = get_font_path()
    
    # 计算可用宽度
    top_max_width = width - (TEXT_SETTINGS['TOP_MARGIN_X'] * 2)
    bottom_max_width = width - (TEXT_SETTINGS['BOTTOM_MARGIN_X'] * 2)
    
    # 计算顶部两行文字的字体大小
    title1_size = calculate_font_size(title1, TEXT_SETTINGS['TITLE_FONT_SIZE'], top_max_width, font_path)
    title2_size = calculate_font_size(title2, TEXT_SETTINGS['TITLE_FONT_SIZE'], top_max_width, font_path)
    top_text_size = min(title1_size, title2_size)
    
    # 底部文字使用独立的字体大小
    bottom_size = calculate_font_size(bottom_text, TEXT_SETTINGS['BOTTOM_FONT_SIZE'], bottom_max_width, font_path)
    
    # 创建字体对象
    title1_font = ImageFont.truetype(font_path, top_text_size)
    title2_font = ImageFont.truetype(font_path, top_text_size)
    bottom_font = ImageFont.truetype(font_path, bottom_size)
    
    def get_text_position(text: str, font: ImageFont.FreeTypeFont, margin_x: int, y_pos: int) -> tuple:
        """计算文字位置，确保在边距范围内居中"""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        available_width = width - (margin_x * 2)
        x = margin_x + (available_width - text_width) // 2
        return x, y_pos, text_width, text_height
    
    # 计算各文字位置
    title1_x, _, title1_width, title1_height = get_text_position(
        title1, title1_font, TEXT_SETTINGS['TOP_MARGIN_X'], TEXT_SETTINGS['TITLE1_Y'])
    title2_x, _, title2_width, title2_height = get_text_position(
        title2, title2_font, TEXT_SETTINGS['TOP_MARGIN_X'], TEXT_SETTINGS['TITLE2_Y'])
    bottom_x, bottom_y, bottom_width, bottom_height = get_text_position(
        bottom_text, bottom_font, TEXT_SETTINGS['BOTTOM_MARGIN_X'], height * 4 // 5)
    
    # 特效参数
    depth = 8              # 3D效果深度
    outline_width = 6      # 描边宽度
    padding = 20           # 底部文字背景内边距
    
    def draw_3d_text(x, y, text, font, color):
        """绘制3D文字效果"""
        for i in range(depth):
            offset = i * 2
            draw.text((x + offset, y + offset), text, font=font, fill=(0, 0, 0, 255))
        
        for offset_x in range(-outline_width, outline_width + 1):
            for offset_y in range(-outline_width, outline_width + 1):
                draw.text((x + offset_x, y + offset_y), text, font=font, fill=(0, 0, 0, 255))
        
        draw.text((x, y), text, font=font, fill=color)
    
    def draw_bottom_text(x, y, text, font):
        """绘制底部文字（黄色背景，黑色文字）"""
        rect_x1 = TEXT_SETTINGS['BOTTOM_BOX_MARGIN']
        rect_y1 = y - padding
        rect_x2 = width - TEXT_SETTINGS['BOTTOM_BOX_MARGIN']
        rect_y2 = y + bottom_height + padding
        
        draw.rectangle([rect_x1, rect_y1, rect_x2, rect_y2], fill=(255, 255, 0, 255))
        
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        x = rect_x1 + (rect_x2 - rect_x1 - text_width) // 2
        
        draw.text((x, y), text, font=font, fill=(0, 0, 0, 255))
    
    # 绘制所有文字
    bright_green = (0, 255, 0, 255)  # 亮绿色
    draw_3d_text(title1_x, TEXT_SETTINGS['TITLE1_Y'], title1, title1_font, bright_green)
    draw_3d_text(title2_x, TEXT_SETTINGS['TITLE2_Y'], title2, title2_font, bright_green)
    draw_bottom_text(bottom_x, bottom_y, bottom_text, bottom_font)
    
    # 保存临时图片
    os.makedirs("temp", exist_ok=True)
    temp_path = os.path.join("temp", "text_overlay.png")
    img.save(temp_path)
    return temp_path 
"""
视频合成工具主入口
"""
import os
import random
import subprocess
import glob
import time
from datetime import datetime
import argparse
import pandas as pd
import gc
import shutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint
from PIL import Image, ImageDraw, ImageFont
from .config.settings import VIDEO_SETTINGS, PATH_SETTINGS, TEXT_SETTINGS, FONT_OPTIONS
from .utils.file_utils import get_random_video, read_text_from_excel, ensure_directory, cleanup_temp_files
from .utils.ffmpeg_utils import get_video_duration, get_video_dimensions
from .core.video_processor import (
    create_blurred_background,
    create_black_background,
    create_main_video,
    create_side_video,
    process_pip2_videos
)
from .core.video_combiner import combine_videos, add_image_overlay

# 创建rich控制台对象
console = Console()

def print_summary(output_path, start_time, video_duration):
    """打印处理总结信息
    Args:
        output_path (str): 输出文件路径
        start_time (float): 开始处理的时间戳
        video_duration (float): 视频时长（秒）
    """
    end_time = time.time()
    process_duration = end_time - start_time
    process_speed = video_duration / process_duration

    # 创建统计表格
    table = Table(title="视频处理统计", show_header=True, header_style="bold magenta")
    table.add_column("项目", style="cyan")
    table.add_column("数值", style="green")

    # 添加统计数据
    table.add_row("输出路径", os.path.abspath(output_path))
    table.add_row("文件大小", f"{os.path.getsize(output_path) / (1024*1024):.2f} MB")
    table.add_row("视频时长", f"{video_duration:.2f} 秒")
    table.add_row("处理用时", f"{process_duration:.2f} 秒")
    table.add_row("处理速度", f"{process_speed:.2f}x")
    table.add_row("完成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 打印表格
    console.print("\n")
    console.print(Panel(table, title="处理完成", border_style="green"))

def cleanup_resources():
    """清理资源和临时文件"""
    try:
        # 清理临时目录
        temp_dir = os.path.normpath(PATH_SETTINGS['TEMP_DIR'])
        if os.path.exists(temp_dir):
            # 先尝试删除目录中的所有文件
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    console.print(f"[red]清理文件失败: {file_path}, 错误: {str(e)}")
            
            # 然后尝试删除目录本身
            try:
                shutil.rmtree(temp_dir)
                console.print(f"[green]已清理临时目录: {temp_dir}")
            except Exception as e:
                console.print(f"[red]删除临时目录失败: {str(e)}")
        
        # 强制垃圾回收
        gc.collect()
        console.print("[green]已释放内存")
        
    except Exception as e:
        console.print(f"[red]清理资源时出错: {str(e)}")

def parse_args():
    """处理命令行参数
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(description='视频合成工具')
    parser.add_argument('background_type', 
                       type=int,
                       choices=[1, 2],
                       help='背景类型：1=虚化背景，2=纯黑背景')
    parser.add_argument('-a', '--auto',
                       action='store_true',
                       help='自动处理文件夹内的所有视频')
    parser.add_argument('--excel',
                       type=str,
                       default='video_texts.xlsx',
                       help='Excel文件路径，包含要添加的文字内容')
    return parser.parse_args()

def get_next_sequence_number(base_dir: str) -> str:
    """
    获取下一个可用的序列号目录
    
    Args:
        base_dir (str): 基础目录路径
        
    Returns:
        str: 下一个可用的4位序列号（如：'0001'）
    """
    if not os.path.exists(base_dir):
        return "0001"
        
    # 获取所有4位数字命名的目录
    existing_dirs = [d for d in os.listdir(base_dir) 
                    if os.path.isdir(os.path.join(base_dir, d)) and 
                    d.isdigit() and len(d) == 4]
    
    if not existing_dirs:
        return "0001"
    
    # 找到最大的序号并加1
    max_num = max(int(d) for d in existing_dirs)
    return f"{max_num + 1:04d}"

def process_single_video(pip1_folder, pip2_folder, outputs_folder, temp_dir, background_type, excel_path):
    """处理单个视频的函数"""
    start_time = time.time()
    
    # 1. 随机选择主视频和对应的Excel文件
    console.print("\n[bold cyan]1. 选择主视频和Excel文件")
    main_video_path, csv_path = get_random_video(pip1_folder)
    
    # 获取视频名称（文件夹名）
    video_name = os.path.basename(os.path.dirname(main_video_path))
    
    # 创建与源视频文件夹同名的输出子文件夹
    output_subfolder = os.path.join(outputs_folder, video_name)
    os.makedirs(output_subfolder, exist_ok=True)
    
    # 获取序列号并创建序列号子文件夹
    sequence_number = get_next_sequence_number(output_subfolder)
    sequence_subfolder = os.path.join(output_subfolder, sequence_number)
    os.makedirs(sequence_subfolder, exist_ok=True)
    console.print(f"[green]创建输出子文件夹: {sequence_subfolder}")
    
    # 读取Excel文件中的文字内容
    title1, title2, bottom_text = read_text_from_excel(csv_path)
    console.print(f"\n使用的文字组合：")
    console.print(f"[bold cyan]顶部主标题：{title1}")
    console.print(f"[bold cyan]顶部副标题：{title2}")
    console.print(f"[bold cyan]底部文字：{bottom_text}")
    
    # 使用三个标题组合作为文件名（去除不合法的文件名字符）
    invalid_chars = '<>:"/\\|?*'
    filename = f"{title1}{title2}{bottom_text}"
    for char in invalid_chars:
        filename = filename.replace(char, '')
    
    # 确保文件名不会重复添加.mp4扩展名
    if not filename.endswith('.mp4'):
        filename = f"{filename}.mp4"
    
    # 构建输出路径（现在包含序列号子文件夹）
    output_path = os.path.join(sequence_subfolder, filename)
    console.print(f"[bold cyan]输出路径: {output_path}")
    
    # 设置高斯模糊程度（较强的模糊效果）
    blur_sigma = VIDEO_SETTINGS['BLUR_SIGMA']
    
    # === 视频尺寸和位置参数 ===
    main_video_scale = VIDEO_SETTINGS['MAIN_VIDEO_SCALE']  # 左侧主视频尺寸
    main_video_x = VIDEO_SETTINGS['MAIN_VIDEO_X']  # 左侧主视频的x坐标
    
    # 获取原始视频尺寸
    width, height = get_video_dimensions(main_video_path)
    # 计算左侧视频的宽度（缩放后）
    main_width = int(width * main_video_scale)
    # 右侧视频应该紧贴着左侧视频
    side_video_x = main_width
    # 计算左侧视频缩放后的高度（减去上下裁剪）
    main_height = int(height * main_video_scale) - 100  # 减去上下各50像素的裁剪
    
    # 2. 创建背景视频（根据用户选择创建模糊或纯黑背景）
    console.print(f"\n[bold cyan]2. 创建{background_type}背景视频")
    blurred_bg = os.path.join(temp_dir, "background.mp4")
    if background_type == 'blur':
        create_blurred_background(main_video_path, blurred_bg, blur_sigma)
    else:  # black
        create_black_background(main_video_path, blurred_bg)
    
    # 3. 创建左侧主视频（缩放并保持音频）
    console.print("\n[bold cyan]3. 创建左侧主视频")
    resized_main = os.path.join(temp_dir, "main.mp4")
    create_main_video(main_video_path, resized_main, scale=main_video_scale)
    
    # 4. 获取视频总时长
    console.print("\n[bold cyan]4. 获取视频时长")
    total_duration = get_video_duration(blurred_bg)
    
    # 5. 创建右侧视频序列
    console.print("\n[bold cyan]5. 创建右侧视频序列")
    side_videos = []
    sequence = process_pip2_videos(main_video_path, pip2_folder)
    
    # 处理所有选中的视频
    for i, video_path in enumerate(sequence):
        output_path_side = os.path.join(temp_dir, f"side_{i}.mp4")
        create_side_video(video_path, output_path_side, target_height=main_height)  # 传递目标高度
        side_videos.append(output_path_side)
    
    # 6. 合并所有视频
    console.print("\n[bold cyan]6. 合并所有视频")
    combine_videos(
        blurred_bg, resized_main, side_videos, os.path.abspath(output_path),
        main_x=main_video_x,
        side_x=side_video_x,
        title1=title1,
        title2=title2,
        bottom_text=bottom_text,
        add_subtitles=True
    )
    
    # 7. 添加图片叠加
    console.print("\n[bold cyan]7. 添加图片叠加")
    tv_overlay_path = os.path.join("assets", "tv.png")
    if os.path.exists(tv_overlay_path):
        temp_output = os.path.join(temp_dir, "temp_output.mp4")
        # 将当前输出文件移动到临时文件
        os.rename(output_path, temp_output)
        # 添加图片叠加
        add_image_overlay(temp_output, tv_overlay_path, output_path)
        # 删除临时文件
        os.remove(temp_output)
        console.print("[green]成功添加电视机边框效果")
    else:
        console.print("[yellow]警告: 未找到tv.png文件，跳过图片叠加步骤")
    
    # 获取视频时长
    video_duration = get_video_duration(output_path)
    
    # 打印处理总结
    print_summary(output_path, start_time, video_duration)
    
    # 返回视频名称
    return video_name

def main(get_name_only=False):
    """主函数
    Args:
        get_name_only: 是否只获取视频名称而不进行处理
    Returns:
        str: 处理的视频名称
    """
    temp_dir = os.path.normpath(PATH_SETTINGS['TEMP_DIR'])
    video_name = None  # 用于存储处理的视频名称
    
    try:
        if not get_name_only:
            console.print(Panel.fit("[bold green]=== 开始视频处理 ===", border_style="green"))
        
        # 解析命令行参数
        args = parse_args()
        
        # 转换参数
        background_type = 'blur' if args.background_type == 1 else 'black'
        if not get_name_only:
            console.print(f"[bold cyan]背景类型: {'虚化背景' if background_type == 'blur' else '纯黑背景'}")
            console.print("提示：输入 1 选择虚化背景")
            console.print("      输入 2 选择纯黑背景")
        
        # === 设置路径 ===
        pip1_folder = os.path.normpath(PATH_SETTINGS['PIP1_FOLDER'])
        pip2_folder = os.path.normpath(PATH_SETTINGS['PIP2_FOLDER'])
        outputs_folder = os.path.normpath(PATH_SETTINGS['OUTPUTS_FOLDER'])
        
        # 创建必要的目录
        if not get_name_only:
            for folder in [temp_dir, outputs_folder]:
                if not os.path.exists(folder):
                    os.makedirs(folder)
                    console.print(f"[green]创建文件夹: {folder}")
        
        if args.auto:
            # 自动处理所有视频
            if not get_name_only:
                console.print("\n[bold cyan]=== 自动处理模式 ===")
            video_files = glob.glob(os.path.join(pip1_folder, "**/*.mp4"), recursive=True)
            total_videos = len(video_files)
            if not get_name_only:
                console.print(f"[bold cyan]找到 {total_videos} 个视频文件需要处理")
            
            for i, video_file in enumerate(video_files, 1):
                if not get_name_only:
                    console.print(f"\n[bold cyan]正在处理第 {i}/{total_videos} 个视频: {os.path.basename(video_file)}")
                try:
                    video_name = process_single_video(pip1_folder, pip2_folder, outputs_folder, temp_dir, background_type, args.excel)
                    if get_name_only:
                        break  # 只需要获取一个视频名称
                    else:
                        # 每处理完一个视频就清理一次
                        cleanup_resources()
                except KeyboardInterrupt:
                    if not get_name_only:
                        console.print("\n[bold red]用户中断处理")
                    break
                except Exception as e:
                    if not get_name_only:
                        console.print(f"[red]处理视频时出错: {str(e)}")
        else:
            # 处理单个视频
            if get_name_only:
                # 只获取视频名称
                main_video_path, _ = get_random_video(pip1_folder)
                video_name = os.path.basename(os.path.dirname(main_video_path))
            else:
                video_name = process_single_video(pip1_folder, pip2_folder, outputs_folder, temp_dir, background_type, args.excel)
                cleanup_resources()
        
    except Exception as e:
        if not get_name_only:
            console.print(f"[red]处理过程中出现错误: {str(e)}")
        
    finally:
        # 返回处理的视频名称
        return video_name

if __name__ == "__main__":
    main() 
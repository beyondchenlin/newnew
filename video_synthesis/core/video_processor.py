"""
视频处理相关的函数模块
"""
import os
import random
from video_synthesis.utils.ffmpeg_utils import run_ffmpeg_command, get_video_duration, get_video_dimensions
from video_synthesis.config.settings import VIDEO_SETTINGS
import glob
import time
from ..utils.file_utils import load_history, save_history
from rich.console import Console

def sanitize_filename(text):
    """处理文件名，移除非法字符
    Args:
        text (str): 原始文本
    Returns:
        str: 处理后的合法文件名
    """
    if not text:
        return "未命名视频"
        
    # 替换Windows文件名中的非法字符
    illegal_chars = r'<>:"/\|?*'
    for char in illegal_chars:
        text = text.replace(char, '_')
    
    # 移除前后空白字符
    text = text.strip()
    
    # 限制长度
    max_length = 50  # 文件名最大长度
    if len(text) > max_length:
        text = text[:max_length]
    
    # 确保文件名不为空
    if not text:
        return "未命名视频"
    
    return text

def get_output_filename(title1="", title2="", bottom_text=""):
    """生成输出文件名
    Args:
        title1 (str): 主标题
        title2 (str): 副标题
        bottom_text (str): 底部文字
    Returns:
        str: 输出文件名
    """
    # 如果所有标题都为空，使用默认名称
    if not any([title1, title2, bottom_text]):
        return "未命名视频.mp4"
    
    # 组合所有非空的标题
    parts = []
    if title1:
        parts.append(title1)
    if title2:
        parts.append(title2)
    if bottom_text:
        parts.append(bottom_text)
    
    # 直接拼接所有部分并添加扩展名
    filename = "".join(parts) + ".mp4"
    
    # 移除不合法的文件名字符
    filename = sanitize_filename(filename)
    
    return filename

def create_blurred_background(input_video, output_video, blur_sigma=None):
    """创建高斯模糊背景视频
    Args:
        input_video (str): 输入视频路径
        output_video (str): 输出视频路径
        blur_sigma (float): 高斯模糊的程度，数值越大越模糊
    """
    if blur_sigma is None:
        blur_sigma = VIDEO_SETTINGS['BLUR_SIGMA']
        
    print(f"\n正在创建高斯模糊背景 (模糊程度: {blur_sigma})")
    print(f"输入视频: {input_video}")
    print(f"输出视频: {output_video}")
    
    # 构建滤镜命令：先高斯模糊，然后叠加黑色遮罩
    filter_complex = [
        f'gblur=sigma={blur_sigma}',  # 高斯模糊
        f'format=rgba',  # 确保支持透明度
        f'split[blur1][blur2]',  # 分成两路
        f'[blur1]format=rgba,geq=r=0:g=0:b=0:a=0.7*255[overlay]',  # 创建70%透明度的黑色遮罩
        f'[blur2][overlay]overlay=0:0'  # 叠加黑色遮罩
    ]
    
    filter_str = ','.join(filter_complex)
    
    cmd = [
        'ffmpeg', '-i', input_video,
        '-vf', filter_str,
        '-an',  # 移除音频
        '-y',   # 覆盖输出文件
        '-progress', 'pipe:1',  # 输出进度信息
        output_video
    ]
    run_ffmpeg_command(cmd, "创建高斯模糊背景")

def create_black_background(video_path, output_path):
    """创建纯黑背景视频
    Args:
        video_path (str): 参考视频路径（用于获取尺寸和时长）
        output_path (str): 输出视频路径
    """
    print(f"\n正在创建纯黑背景视频")
    print(f"参考视频: {video_path}")
    print(f"输出视频: {output_path}")
    
    width, height = get_video_dimensions(video_path)
    duration = get_video_duration(video_path)
    
    print(f"视频信息: {width}x{height}, 时长: {duration:.2f}秒")
    
    cmd = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'color=c=black:s={width}x{height}:d={duration}',
        '-c:v', 'libx264',
        '-tune', 'stillimage',
        '-pix_fmt', 'yuv420p',
        '-y',
        output_path
    ]
    run_ffmpeg_command(cmd, "创建纯黑背景")

def create_main_video(input_video, output_video, scale=None, outline_enabled=False):
    """创建左侧主视频，并添加字幕
    Args:
        input_video (str): 输入视频路径
        output_video (str): 输出视频路径
        scale (float): 缩放比例
        outline_enabled (bool): 是否启用字幕描边，默认False
    """
    if scale is None:
        scale = VIDEO_SETTINGS['MAIN_VIDEO_SCALE']
        
    if not os.path.exists(input_video):
        raise Exception(f"输入视频文件不存在: {input_video}")
    
    print(f"输入视频路径: {input_video}")
    print(f"输出视频路径: {output_video}")
    print(f"缩放比例: {scale}")
    
    # 获取视频尺寸
    width, height = get_video_dimensions(input_video)
    
    # 计算输出尺寸（确保是2的倍数）
    out_width = int(width * scale)
    out_height = int(height * scale)
    if out_width % 2 != 0:
        out_width += 1
    if out_height % 2 != 0:
        out_height += 1
    
    # 计算裁切后的高度
    crop_margin = VIDEO_SETTINGS['CROP_MARGIN']
    crop_height = out_height - (crop_margin * 2)
    
    print(f"缩放后视频尺寸: {out_width}x{out_height}")
    print(f"裁切后视频尺寸: {out_width}x{crop_height}")
    
    # 第一步：缩放和裁剪视频
    temp_output = output_video.replace('.mp4', '_temp.mp4')
    filters = [
        f'scale={out_width}:{out_height}',  # 先缩放
        f'crop=iw:ih-{crop_margin*2}:0:{crop_margin}'  # 然后裁切上下各50像素
    ]
    
    filter_str = ','.join(filters)
    cmd = [
        'ffmpeg', '-i', input_video,
        '-vf', filter_str,
        '-c:v', 'libx264',  # 视频编码器
        '-preset', 'medium',  # 编码器预设
        '-c:a', 'copy',      # 复制音频流
        '-y',
        temp_output
    ]
    run_ffmpeg_command(cmd, "创建临时视频")
    
    # 第二步：添加字幕
    # 获取字体文件路径
    font_path = os.path.abspath("fonts/方正粗黑宋简体.ttf")
    if not os.path.exists(font_path):
        print(f"警告: 字体文件不存在: {font_path}")
        if os.path.exists(temp_output):
            os.rename(temp_output, output_video)
        return
        
    # 查找字幕文件
    video_dir = os.path.dirname(input_video)  # 获取视频所在目录
    video_name = os.path.splitext(os.path.basename(input_video))[0]
    en_srt = os.path.join(video_dir, f"{video_name}_en.srt")  # 查找英文字幕
    
    if os.path.exists(en_srt):
        # 使用英文字幕文件
        print(f"\n使用英文字幕文件: {os.path.basename(en_srt)}")
        en_srt = os.path.abspath(en_srt)
        
        # 检查字幕文件内容
        try:
            with open(en_srt, 'r', encoding='utf-8') as f:
                srt_content = f.read(1024)  # 读取前1KB内容
                print("\n字幕文件预览:")
                print(srt_content[:200] + "...")  # 显示前200个字符
                
            # 转义字体路径中的特殊字符
            font_path = font_path.replace('\\', '/').replace(':', r'\:')
            srt_path = en_srt.replace('\\', '/').replace(':', r'\:')
            
            # 添加字幕滤镜，使用更完整的参数
            subtitle_style = [
                "Fontname=Microsoft YaHei",  # 使用微软雅黑的英文名称
                "Fontsize=12",  # 字号12
                "PrimaryColour=&H000000",  # 白色文字
                "Shadow=0",
                "MarginV=20",
                "Alignment=2",  # 居中对齐
                "Outline=0"  # 显式设置无描边
            ]
            
            # 如果启用描边，重新设置描边参数
            if outline_enabled:
                subtitle_style = [
                    "Fontname=Microsoft YaHei",  # 使用微软雅黑的英文名称
                    "Fontsize=12",  # 字号12
                    "PrimaryColour=&HFFFFFF",  # 白色文字
                    "Shadow=0",
                    "MarginV=20",
                    "Alignment=2",  # 居中对齐
                    "OutlineColour=&H000000",  # 黑色描边
                    "Outline=1"  # 描边宽度为1
                ]
            
            # 将样式列表转换为字符串，用逗号连接
            subtitle_style_str = ','.join(subtitle_style)
            
            subtitle_filter = (
                f"subtitles='{srt_path}'"
                ":charenc=UTF-8"  # 指定字幕编码
                f":force_style='{subtitle_style_str}'"
            )
            
            print(f"\n使用字体: {font_path}")
            print(f"字幕滤镜: {subtitle_filter}")
            
            cmd = [
                'ffmpeg', '-i', temp_output,
                '-vf', subtitle_filter,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-c:a', 'copy',
                '-y',
                output_video
            ]
            run_ffmpeg_command(cmd, "添加字幕")
            
            # 删除临时文件
            if os.path.exists(temp_output):
                os.remove(temp_output)
                
        except Exception as e:
            print(f"警告: 添加字幕时出错: {str(e)}")
            print("继续处理视频但不添加字幕...")
            # 如果添加字幕失败，直接使用临时文件作为最终输出
            if os.path.exists(temp_output):
                os.rename(temp_output, output_video)
    else:
        print(f"警告: 未找到英文字幕文件: {en_srt}")
        # 如果没有字幕文件，直接使用临时文件作为最终输出
        if os.path.exists(temp_output):
            os.rename(temp_output, output_video)

def create_side_video(input_video, output_video, scale=None, target_height=None):
    """创建右侧视频，确保与左侧视频顶底对齐
    Args:
        input_video (str): 输入视频路径
        output_video (str): 输出视频路径
        scale (float): 缩放比例（如果指定了target_height则忽略此参数）
        target_height (int): 目标高度（与左侧视频对齐，已经是裁切后的高度）
    """
    width, height = get_video_dimensions(input_video)
    
    # 计算目标尺寸
    if target_height is not None:
        # 计算缩放比例 = 目标高度(裁切后) / (原始高度 - 100)
        # 因为我们需要考虑到最终会裁切掉上下各50像素
        scale = (target_height + 100) / height
        target_width = int(width * scale)
        target_height = int(height * scale)
        print(f"根据目标高度 {target_height}px 计算缩放比例: {scale:.2%}")
    else:
        # 否则使用指定的缩放比例
        target_width = int(width * scale)
        target_height = int(height * scale)
        print(f"使用指定的缩放比例: {scale:.2%}")
    
    # 确保尺寸是2的倍数
    if target_width % 2 != 0:
        target_width += 1
    if target_height % 2 != 0:
        target_height += 1
    
    print(f"目标视频尺寸: {target_width}x{target_height}")
    
    # 构建滤镜命令
    filter_complex = [
        f'scale={target_width}:{target_height}',
        f'crop=iw:ih-100:0:50'  # 上下各裁切50像素
    ]
    
    filter_str = ','.join(filter_complex)
    
    cmd = [
        'ffmpeg', '-i', input_video,
        '-vf', filter_str,
        '-c:v', 'libx264',     # 视频编码器
        '-preset', 'ultrafast', # 最快的编码速度
        '-crf', '28',          # 较低的视频质量（文件更小，处理更快）
        '-tune', 'fastdecode', # 优化解码速度
        '-an',                 # 移除音频
        '-y',
        output_video
    ]
    run_ffmpeg_command(cmd, f"创建右侧视频: {os.path.basename(input_video)}")

def generate_pip2_sequence(pip2_folder, target_duration):
    """按随机逻辑生成右侧视频序列，并确保总时长匹配目标时长
    Args:
        pip2_folder (str): pip2视频文件夹路径
        target_duration (float): 目标总时长（主视频时长）
    Returns:
        list: 视频路径列表
    """
    sequence = []
    folders = []
    
    # 获取所有子文件夹
    for item in os.listdir(pip2_folder):
        folder_path = os.path.join(pip2_folder, item)
        if os.path.isdir(folder_path):
            folders.append(folder_path)
    
    if not folders:
        raise Exception("没有找到可用的视频文件夹")
    
    print(f"\n找到 {len(folders)} 个子文件夹")
    
    def generate_one_round():
        """生成一轮完全随机的视频序列
        Returns:
            list: 一轮的视频序列
        """
        one_round_sequence = []
        available_folders = folders.copy()  # 创建可用文件夹列表的副本
        
        # 第一组：随机选择1个文件夹
        if available_folders:
            folder = random.choice(available_folders)
            video1 = os.path.join(folder, "1.mp4")
            video2 = os.path.join(folder, "2.mp4")
            if os.path.exists(video1) and os.path.exists(video2):
                one_round_sequence.extend([video1, video2])
            available_folders.remove(folder)  # 从可用列表中移除已使用的文件夹
        
        # 第二组：随机选择2个文件夹
        if len(available_folders) >= 2:
            selected_folders = random.sample(available_folders, 2)
            for folder in selected_folders:
                video1 = os.path.join(folder, "1.mp4")
                if os.path.exists(video1):
                    one_round_sequence.append(video1)
            for folder in selected_folders:
                video2 = os.path.join(folder, "2.mp4")
                if os.path.exists(video2):
                    one_round_sequence.append(video2)
            for folder in selected_folders:
                available_folders.remove(folder)
        
        # 第三组：随机选择3个文件夹
        if len(available_folders) >= 3:
            selected_folders = random.sample(available_folders, 3)
            for folder in selected_folders:
                video1 = os.path.join(folder, "1.mp4")
                if os.path.exists(video1):
                    one_round_sequence.append(video1)
            for folder in selected_folders:
                video2 = os.path.join(folder, "2.mp4")
                if os.path.exists(video2):
                    one_round_sequence.append(video2)
        
        return one_round_sequence
    
    # 生成第一轮序列并计算时长
    first_round = generate_one_round()
    one_round_duration = sum(get_video_duration(v) for v in first_round)
    
    print(f"\n一轮序列信息:")
    print(f"- 视频数量: {len(first_round)}")
    print(f"- 总时长: {one_round_duration:.2f}秒")
    
    # 计算需要重复的轮数
    needed_rounds = int(target_duration / one_round_duration) + 1
    print(f"\n目标时长: {target_duration:.2f}秒")
    print(f"需要重复: {needed_rounds}轮")
    
    # 生成完整序列，每轮都重新随机
    sequence.extend(first_round)  # 添加第一轮
    for round in range(1, needed_rounds):
        print(f"\n开始第{round + 1}轮添加...")
        round_sequence = generate_one_round()
        sequence.extend(round_sequence)
    
    print(f"\n序列生成完成:")
    print(f"- 总视频数量: {len(sequence)}")
    total_duration = sum(get_video_duration(v) for v in sequence)
    print(f"- 总时长: {total_duration:.2f}秒")
    
    return sequence

def process_pip2_videos(main_video_path, pip2_folder):
    """处理pip2文件夹中的视频
    Args:
        main_video_path (str): 主视频路径
        pip2_folder (str): pip2视频文件夹路径
    Returns:
        list: 处理后的视频路径列表
    """
    # 获取主视频时长
    target_duration = get_video_duration(main_video_path)
    print(f"\n主视频时长: {target_duration:.2f}秒")
    
    # 生成视频序列
    return generate_pip2_sequence(pip2_folder, target_duration)

def combine_videos(background_video, main_video, side_videos, output_path, main_x=0, side_x=None, title1="默认主标题", title2="默认副标题", bottom_text="默认底部文字"):
    """合并所有视频
    Args:
        background_video (str): 背景视频路径
        main_video (str): 主视频路径
        side_videos (list): 右侧视频路径列表
        output_path (str): 输出文件路径
        main_x (int): 左侧主视频的x坐标
        side_x (int): 右侧视频的x坐标，如果为None则自动计算
        title1 (str): 顶部主标题
        title2 (str): 顶部副标题
        bottom_text (str): 底部文字
    Returns:
        str: 输出文件路径
    """
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)
    
    # 确保输出路径不会重复添加文件名
    if output_path.endswith('.mp4.mp4'):
        output_path = output_path[:-4]
    
    print(f"\n输出文件: {os.path.basename(output_path)}")
    print(f"输出目录: {output_dir}")
    
    # 获取主视频尺寸和时长
    width, height = get_video_dimensions(main_video)
    main_duration = get_video_duration(main_video)
    
    # 如果没有指定右侧视频位置，则紧贴左侧视频
    if side_x is None:
        side_x = width
    
    # 构建视频合并的filter_complex命令
    inputs = [background_video, main_video] + side_videos
    input_args = []
    for input_file in inputs:
        input_args.extend(['-i', input_file])
    
    filter_complex = []
    # 设置背景视频
    filter_complex.append('[0:v]setpts=PTS-STARTPTS[bg]')
    # 设置主视频
    filter_complex.append('[1:v]setpts=PTS-STARTPTS[main]')
    # 叠加视频到背景
    filter_complex.append(f'[bg][main]overlay=x={main_x}:y=(H-h)/2[bg1]')
    
    # 处理右侧视频序列
    last_bg = 'bg1'
    current_time = 0
    
    # 获取每个视频的时长
    video_durations = []
    for video in side_videos:
        duration = get_video_duration(video)
        video_durations.append(duration)
        print(f"视频时长: {duration:.2f}秒")
    
    # 处理每个视频
    for i in range(len(side_videos)):
        # 如果当前时间已经超过主视频时长，就不再添加更多视频
        if current_time >= main_duration:
            break
            
        filter_complex.append(f'[{i+2}:v]setpts=PTS-STARTPTS+{current_time}/TB[side{i}]')
        next_bg = f'bg{i+2}'
        
        # 计算这个视频的结束时间，如果超过主视频时长，则裁切
        end_time = min(current_time + video_durations[i], main_duration)
        
        filter_complex.append(
            f'[{last_bg}][side{i}]overlay=x={side_x}:y=(H-h)/2:'
            f'enable=\'between(t,{current_time},{end_time})\''
            f'[{next_bg}]'
        )
        last_bg = next_bg
        current_time += video_durations[i]
    
    # 完成视频合并
    filter_str = ';'.join(filter_complex)
    cmd = ['ffmpeg', '-y'] + input_args + [
        '-filter_complex', filter_str,
        '-map', f'[{last_bg}]',
        '-map', '1:a',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-tune', 'fastdecode',
        '-profile:v', 'baseline',
        '-level', '3.0',
        '-maxrate', '2000k',
        '-bufsize', '4000k',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        output_path
    ]
    
    print("\n完整的ffmpeg命令:")
    print(' '.join(cmd))
    
    run_ffmpeg_command(cmd, "合并视频")
    
    return output_path 
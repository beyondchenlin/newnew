"""
视频合成相关的函数模块
"""
import os
import tempfile
import logging
from datetime import datetime
from video_synthesis.config.settings import VIDEO_SETTINGS, PATH_SETTINGS, TEXT_SETTINGS
from video_synthesis.utils.ffmpeg_utils import get_video_duration, get_video_dimensions, run_ffmpeg_command
from video_synthesis.core.text_processor import create_text_overlay
from video_synthesis.core.video_processor import get_output_filename
from rich import console

console = console.Console()

def setup_logger():
    """设置日志记录器"""
    # 确保logs目录存在
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 创建一个以时间戳命名的日志文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"subtitle_process_{timestamp}.log")
    
    # 配置日志记录器
    logger = logging.getLogger('subtitle_processor')
    logger.setLevel(logging.DEBUG)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    logger.addHandler(file_handler)
    
    return logger

# 创建日志记录器
logger = setup_logger()

def parse_srt_time(time_str, add_delay=0):
    """解析SRT时间格式为ASS时间格式，并可选添加延迟
    Args:
        time_str: SRT格式时间字符串
        add_delay: 需要添加的延迟秒数
    Returns:
        ASS格式时间字符串
    """
    h, m, s = time_str.split(':')
    s, ms = s.split(',')
    # 将时间转换为秒
    total_seconds = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000 + add_delay
    
    # 转回时分秒格式
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    centiseconds = int((total_seconds * 100) % 100)
    
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

def parse_time_to_seconds(time_str):
    """将ASS时间格式转换为秒数
    Args:
        time_str: ASS格式时间字符串 (h:mm:ss.cc)
    Returns:
        float: 总秒数
    """
    h, m, s = time_str.split(':')
    s, cs = s.split('.')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100

def add_chinese_line_breaks(text, max_chars=15):
    """
    为中文文本添加软换行符
    Args:
        text: 原始中文文本
        max_chars: 每行最大字符数
    Returns:
        处理后的文本
    """
    if len(text) <= max_chars:
        return text
    
    result = []
    for i in range(0, len(text), max_chars):
        result.append(text[i:i + max_chars])
    return '\\N'.join(result)

def merge_subtitles(zh_srt, en_srt):
    """合并中英文字幕为ASS格式"""
    logger.info("\n" + "="*50)
    logger.info("开始字幕合并处理")
    logger.info("="*50)
    logger.info(f"中文字幕文件: {zh_srt}")
    logger.info(f"英文字幕文件: {en_srt}")
    
    # ASS文件头部
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CN,微软雅黑,50,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,3,0,0,2,30,30,160,1
Style: EN,微软雅黑,50,&H00000000,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,8,30,30,160,1
Style: EN_BOX,Arial,20,&H0000FFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,30,30,160,1
Style: CN_Hidden,微软雅黑,50,&HFFFFFFFF,&H000000FF,&HFF000000,&HFF000000,1,0,0,0,100,100,0,0,3,0,0,2,30,30,160,1
Style: EN_Hidden,微软雅黑,50,&HFF000000,&H000000FF,&HFF000000,&HFF000000,1,0,0,0,100,100,0,0,1,0,0,8,30,30,160,1
Style: EN_BOX_Hidden,Arial,20,&HFF00FFFF,&H000000FF,&HFF000000,&HFF000000,0,0,0,0,100,100,0,0,1,0,0,8,30,30,160,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    # 检查输入文件
    if not os.path.exists(zh_srt):
        logger.error(f"中文字幕文件不存在: {zh_srt}")
        return None
    if not os.path.exists(en_srt):
        logger.error(f"英文字幕文件不存在: {en_srt}")
        return None
    
    # 获取视频文件夹名称和路径
    video_folder = os.path.basename(os.path.dirname(zh_srt))
    video_dir = os.path.dirname(zh_srt)
    
    # 生成字幕文件路径（使用时间戳，避免冲突）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    merged_ass = os.path.join(video_dir, f"subtitle_{timestamp}.ass").replace("\\", "/")
    logger.info(f"合并后的字幕文件将保存为: {merged_ass}")
    
    try:
        # 读取中文字幕
        with open(zh_srt, 'r', encoding='utf-8') as f:
            zh_content = f.read()
            logger.info(f"成功读取中文字幕，大小: {len(zh_content)} 字节")
        
        # 读取英文字幕
        with open(en_srt, 'r', encoding='utf-8') as f:
            en_content = f.read()
            logger.info(f"成功读取英文字幕，大小: {len(en_content)} 字节")
        
        # 解析字幕内容
        zh_blocks = zh_content.strip().split('\n\n')
        en_blocks = en_content.strip().split('\n\n')
        logger.info(f"中文字幕块数: {len(zh_blocks)}")
        logger.info(f"英文字幕块数: {len(en_blocks)}")
        
        # 写入ASS文件
        with open(merged_ass, 'w', encoding='utf-8') as f:
            # 写入头部
            f.write(ass_header)
            logger.info("\n=== ASS文件头部写入成功 ===")
            
            # 写入字幕内容
            written_lines = 0
            hidden_lines = 0
            normal_lines = 0
            cross_six_lines = 0
            
            def write_subtitle_with_box(f, start_time, end_time, text, is_hidden=False):
                """写入带背景框的字幕"""
                style_suffix = "_Hidden" if is_hidden else ""
                # 背景框
                f.write(f"Dialogue: 0,{start_time},{end_time},EN_BOX{style_suffix},,30,30,160,,{{\\p1}}m 0 0 l 600 0 600 60 0 60{{\\p0}}\n")
                # 文本
                f.write(f"Dialogue: 1,{start_time},{end_time},EN{style_suffix},,30,30,160,,{text}\n")
                return 2  # 返回写入的行数
            
            for i in range(len(zh_blocks)):
                zh_lines = zh_blocks[i].split('\n')
                en_lines = en_blocks[i].split('\n')
                
                if len(zh_lines) >= 3 and len(en_lines) >= 3:
                    # 解析时间
                    zh_times = zh_lines[1].split(' --> ')
                    start_time = parse_srt_time(zh_times[0].strip())
                    end_time = parse_srt_time(zh_times[1].strip())
                    
                    # 获取文本
                    zh_text = ''.join(zh_lines[2:])
                    en_text = ''.join(en_lines[2:])
                    
                    # 只对中文文本添加换行处理
                    zh_text = add_chinese_line_breaks(zh_text)
                    
                    # 写入中英文字幕，根据时间选择样式
                    start_seconds = parse_time_to_seconds(start_time)
                    end_seconds = parse_time_to_seconds(end_time)
                    
                    if start_seconds < 4:
                        logger.info(f"\n字幕块 {i+1}:")
                        logger.info(f"时间: {start_time} --> {end_time}")
                        logger.info(f"中文文本: {zh_text}")
                        logger.info(f"英文文本: {en_text}")
                        logger.info(f"使用Hidden样式 (0-4秒)")
                        
                        # 4秒内的字幕使用带透明度的样式
                        f.write(f"Dialogue: 0,{start_time},0:00:04.00,CN_Hidden,,30,30,160,,{zh_text}\n")
                        written_lines += write_subtitle_with_box(f, start_time, "0:00:04.00", en_text, True)
                        hidden_lines += 3
                        
                        # 4秒后的部分使用普通样式
                        if end_seconds > 4:
                            logger.info(f"字幕跨越4秒时间点，添加正常样式部分 (4秒-{end_time})")
                            f.write(f"Dialogue: 0,0:00:04.00,{end_time},CN,,30,30,160,,{zh_text}\n")
                            written_lines += write_subtitle_with_box(f, "0:00:04.00", end_time, en_text)
                            cross_six_lines += 3
                    else:
                        logger.info(f"\n字幕块 {i+1}:")
                        logger.info(f"时间: {start_time} --> {end_time}")
                        logger.info(f"中文文本: {zh_text}")
                        logger.info(f"英文文本: {en_text}")
                        logger.info("使用正常样式 (>4秒)")
                        
                        # 4秒后的字幕直接使用普通样式
                        f.write(f"Dialogue: 0,{start_time},{end_time},CN,,30,30,160,,{zh_text}\n")
                        written_lines += write_subtitle_with_box(f, start_time, end_time, en_text)
                        normal_lines += 3
                    
                    written_lines += 1
            
            logger.info("\n=== 字幕写入统计 ===")
            logger.info(f"总写入行数: {written_lines}")
            logger.info(f"Hidden样式行数: {hidden_lines}")
            logger.info(f"正常样式行数: {normal_lines}")
            logger.info(f"跨越4秒的行数: {cross_six_lines}")
        
        # 验证生成的文件
        if os.path.exists(merged_ass):
            file_size = os.path.getsize(merged_ass)
            logger.info("\n=== 文件验证 ===")
            logger.info(f"文件大小: {file_size} 字节")
            
            # 验证文件格式
            with open(merged_ass, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.info("格式验证:")
                
                # 验证必要的节段
                if "[Script Info]" in content:
                    logger.info("✓ 包含 [Script Info] 节段")
                else:
                    logger.error("× 缺少 [Script Info] 节段")
                
                if "[V4+ Styles]" in content:
                    logger.info("✓ 包含 [V4+ Styles] 节段")
                else:
                    logger.error("× 缺少 [V4+ Styles] 节段")
                
                if "[Events]" in content:
                    logger.info("✓ 包含 [Events] 节段")
                else:
                    logger.error("× 缺少 [Events] 节段")
                
                # 验证样式定义
                if "Style: CN," in content and "Style: EN," in content:
                    logger.info("✓ 包含必要的样式定义")
                else:
                    logger.error("× 缺少必要的样式定义")
                
                # 验证字幕行
                dialogue_count = content.count("Dialogue: ")
                if dialogue_count > 0:
                    logger.info(f"✓ 包含 {dialogue_count} 行字幕")
                else:
                    logger.error("× 没有找到字幕行")
                
                # 验证时间格式
                import re
                time_pattern = r'\d:\d{2}:\d{2}\.\d{2}'
                if re.search(time_pattern, content):
                    logger.info("✓ 时间格式正确")
                else:
                    logger.error("× 时间格式可能有误")
            
            return merged_ass
        else:
            logger.error("字幕文件生成失败")
            return None
            
    except Exception as e:
        logger.error(f"字幕合并过程出错: {str(e)}")
        return None

def combine_videos(background_video, main_video, side_videos, output_path, main_x=None, side_x=None, title1="默认主标题", title2="默认副标题", bottom_text="默认底部文字", add_subtitles=True):
    """合并所有视频
    Args:
        background_video: 背景视频路径
        main_video: 主视频路径
        side_videos: 侧边视频路径列表
        output_path: 输出视频路径
        main_x: 主视频X坐标
        side_x: 侧边视频X坐标
        title1: 主标题
        title2: 副标题
        bottom_text: 底部文字
        add_subtitles: 是否添加SRT字幕，默认True
    """
    logger.info("\n" + "="*50)
    logger.info("视频合成处理开始")
    logger.info("="*50)
    
    # 记录输入参数
    logger.info("\n=== 输入参数 ===")
    logger.info(f"背景视频: {background_video}")
    logger.info(f"主视频: {main_video}")
    logger.info(f"侧边视频数量: {len(side_videos)}")
    for i, video in enumerate(side_videos):
        logger.info(f"侧边视频 {i+1}: {video}")
    logger.info(f"输出路径: {output_path}")
    logger.info(f"主视频X坐标: {main_x}")
    logger.info(f"侧边视频X坐标: {side_x}")
    logger.info(f"主标题: {title1}")
    logger.info(f"副标题: {title2}")
    logger.info(f"底部文字: {bottom_text}")
    
    if main_x is None:
        main_x = VIDEO_SETTINGS['MAIN_VIDEO_X']
    
    # 获取主视频尺寸
    main_width, main_height = get_video_dimensions(main_video)
    logger.info(f"\n=== 视频尺寸信息 ===")
    logger.info(f"主视频原始尺寸: {main_width}x{main_height}")
    
    # 如果没有指定右侧视频位置，则紧贴左侧视频
    if side_x is None:
        side_x = main_width
        logger.info(f"自动计算侧边视频X坐标: {side_x}")
    
    # 获取背景视频尺寸
    width, height = get_video_dimensions(background_video)
    logger.info(f"背景视频尺寸: {width}x{height}")
    
    # 字幕处理
    merged_ass = None
    if add_subtitles:
        logger.info("\n=== 字幕处理 ===")
        zh_srt = None
        en_srt = None
        
        # 获取原始视频路径（从main_video路径反推）
        temp_dir = os.path.normpath(PATH_SETTINGS['TEMP_DIR'])
        if main_video.startswith(temp_dir):
            # 如果是临时目录中的文件，需要找到原始视频
            original_video_name = os.path.splitext(os.path.basename(main_video))[0]
            if original_video_name == "main":  # 如果是处理后的主视频
                # 搜索pip1_videos目录
                pip1_folder = os.path.normpath(PATH_SETTINGS['PIP1_FOLDER'])
                logger.info(f"搜索原始视频目录: {pip1_folder}")
                
                # 递归搜索所有mp4文件
                for root, _, files in os.walk(pip1_folder):
                    for file in files:
                        if file.endswith('.mp4'):
                            video_name = os.path.splitext(file)[0]
                            # 检查同目录下是否存在对应的字幕文件
                            potential_zh_srt = os.path.join(root, f"{video_name}_zh.srt")
                            potential_en_srt = os.path.join(root, f"{video_name}_en.srt")
                            if os.path.exists(potential_zh_srt) and os.path.exists(potential_en_srt):
                                logger.info(f"找到原始视频及其字幕文件: {os.path.join(root, file)}")
                                zh_srt = potential_zh_srt
                                en_srt = potential_en_srt
                                break
        else:
            # 直接使用主视频所在目录
            main_video_dir = os.path.dirname(main_video)
            main_video_name = os.path.splitext(os.path.basename(main_video))[0]
            zh_srt = os.path.join(main_video_dir, f"{main_video_name}_zh.srt")
            en_srt = os.path.join(main_video_dir, f"{main_video_name}_en.srt")
        
        # 检查并处理字幕文件
        if zh_srt and en_srt and os.path.exists(zh_srt) and os.path.exists(en_srt):
            logger.info(f"找到字幕文件:")
            logger.info(f"中文字幕: {zh_srt}")
            logger.info(f"英文字幕: {en_srt}")
            merged_ass = merge_subtitles(zh_srt, en_srt)
        else:
            logger.warning("未找到完整的字幕文件，将跳过字幕处理")
    else:
        logger.info("字幕添加功能已禁用")
    
    # 创建文字叠加图片
    text_overlay = create_text_overlay(title1, title2, bottom_text, width, height)
    
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
    
    # 处理每个视频
    for i in range(len(side_videos)):
        filter_complex.append(f'[{i+2}:v]setpts=PTS-STARTPTS+{current_time}/TB[side{i}]')
        next_bg = f'bg{i+2}'
        filter_complex.append(
            f'[{last_bg}][side{i}]overlay=x={side_x}:y=(H-h)/2:'
            f'enable=\'between(t,{current_time},{current_time + video_durations[i]})\''
            f'[{next_bg}]'
        )
        last_bg = next_bg
        current_time += video_durations[i]
    
    # 添加文字叠加图片
    input_args.extend(['-i', text_overlay])
    next_bg = f'{last_bg}_text'
    
    # 获取文字显示的持续时间配置
    text_duration = TEXT_SETTINGS.get('TEXT_OVERLAY_DURATION', 4)  # 默认4秒
    fade_in = TEXT_SETTINGS.get('FADE_IN_DURATION', 0)  # 默认0秒，不使用淡入
    fade_out = TEXT_SETTINGS.get('FADE_OUT_DURATION', 0.5)  # 默认0.5秒淡出
    
    # 根据是否需要淡入淡出效果构建不同的filter complex
    if fade_in == 0 and fade_out == 0:
        # 不使用任何淡入淡出效果
        filter_complex.append(
            f'[{last_bg}][{len(inputs)}:v]overlay=0:0:'
            f'enable=\'between(t,0,{text_duration})\''  # 直接控制文字显示的时间范围
            f'[{next_bg}]'
        )
    elif fade_in == 0:
        # 只使用淡出效果
        filter_complex.append(
            f'[{len(inputs)}:v]format=rgba,'  # 确保使用rgba格式以支持透明度
            f'fade=out:st={text_duration-fade_out}:d={fade_out}[text_faded]'  # 只有淡出效果
        )
        filter_complex.append(
            f'[{last_bg}][text_faded]overlay=0:0:'
            f'enable=\'between(t,0,{text_duration})\''  # 控制文字显示的时间范围
            f'[{next_bg}]'
        )
    else:
        # 使用完整的淡入淡出效果
        filter_complex.append(
            f'[{len(inputs)}:v]format=rgba,'  # 确保使用rgba格式以支持透明度
            f'fade=in:st=0:d={fade_in}:'      # 淡入效果
            f'fade=out:st={text_duration-fade_out}:d={fade_out}[text_faded]'  # 淡出效果
        )
        filter_complex.append(
            f'[{last_bg}][text_faded]overlay=0:0:'
            f'enable=\'between(t,0,{text_duration})\''  # 控制文字显示的时间范围
            f'[{next_bg}]'
        )
    
    last_bg = next_bg
    
    # 添加字幕（如果启用并且存在）
    if add_subtitles and merged_ass and os.path.exists(merged_ass):
        merged_ass = merged_ass.replace("\\", "/")
        filter_complex.append(f'[{last_bg}]ass={merged_ass}[final]')
        logger.info("字幕添加成功")
    else:
        filter_complex.append(f'[{last_bg}]null[final]')
        logger.info("跳过字幕添加")
    
    # 完成视频合并
    filter_str = ';'.join(filter_complex)
    cmd = ['ffmpeg', '-y'] + input_args + [
        '-filter_complex', filter_str,
        '-map', '[final]',
        '-map', '1:a',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-tune', 'fastdecode',
        '-profile:v', 'baseline',
        '-level', '3.0',
        '-maxrate', '2000k',
        '-bufsize', '4000k',
        '-pix_fmt', 'yuv420p',
        '-r', '30',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        output_path
    ]
    
    print("\n完整的ffmpeg命令:")
    print(' '.join(cmd))
    
    run_ffmpeg_command(cmd, "合并视频")
    
    return output_path

def add_image_overlay(input_video: str, overlay_image: str, output_video: str):
    """
    在视频上叠加图片
    
    Args:
        input_video (str): 输入视频路径
        overlay_image (str): 叠加图片路径
        output_video (str): 输出视频路径
    """
    try:
        # 获取视频尺寸
        width, height = get_video_dimensions(input_video)
        
        # 构建ffmpeg命令
        command = [
            'ffmpeg', '-y',
            '-i', input_video,
            '-i', overlay_image,
            '-filter_complex', f'[1:v]scale=-1:-1[overlay];[0:v][overlay]overlay=0:0',
            '-c:a', 'copy',
            output_video
        ]
        
        # 执行命令
        run_ffmpeg_command(command)
        console.print(f"[green]成功添加图片叠加效果")
        
    except Exception as e:
        console.print(f"[red]添加图片叠加时出错: {str(e)}")
        raise e
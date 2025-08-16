"""
字幕处理一体化脚本：分析字幕、生成音频并剪辑视频
"""

import os
import sys
import json
import logging
import glob
from datetime import datetime
from video_synthesis.core.deepseek import SubtitleAnalyzer, save_analysis_results
from video_synthesis.core.tts_huoshan import TTSConverter
from video_synthesis.core.video_clipper import VideoClipper

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/subtitle_process_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

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

def find_english_subtitle(video_name: str) -> str:
    """
    根据视频名称查找对应的英文字幕文件
    
    Args:
        video_name (str): 视频名称（不含扩展名）
        
    Returns:
        str: 字幕文件路径，如果未找到则返回None
    """
    # 构建视频目录路径
    video_dir = os.path.join("assets", "pip1_videos", video_name)
    if not os.path.exists(video_dir):
        logging.error(f"视频目录不存在: {video_dir}")
        return None
        
    # 查找英文字幕文件
    srt_pattern = os.path.join(video_dir, "*_en.srt")
    srt_files = glob.glob(srt_pattern)
    
    if not srt_files:
        logging.error(f"未找到英文字幕文件: {srt_pattern}")
        return None
        
    # 返回找到的第一个英文字幕文件
    return srt_files[0]

def find_video_file(video_name: str) -> str:
    """
    根据视频名称查找对应的视频文件
    
    Args:
        video_name (str): 视频名称（不含扩展名）
        
    Returns:
        str: 视频文件路径，如果未找到则返回None
    """
    video_dir = os.path.join("assets", "pip1_videos", video_name)
    if not os.path.exists(video_dir):
        logging.error(f"视频目录不存在: {video_dir}")
        return None
        
    # 支持的视频格式
    video_patterns = [
        os.path.join(video_dir, f"{video_name}.mp4"),
        os.path.join(video_dir, f"{video_name}.mkv"),
        os.path.join(video_dir, f"{video_name}.avi"),
        os.path.join(video_dir, f"{video_name}.mov")
    ]
    
    for pattern in video_patterns:
        if os.path.exists(pattern):
            return pattern
            
    logging.error(f"未找到视频文件: {video_name}.*")
    return None

def process_subtitle(video_name: str = None, subtitle_file: str = None, output_dir: str = "subtitles", voice_type: str = "影视解说小帅"):
    """
    处理字幕文件：分析、生成音频并剪辑视频
    
    Args:
        video_name (str): 视频名称（如果提供，将自动查找对应的英文字幕）
        subtitle_file (str): 字幕文件路径（如果提供video_name，则忽略此参数）
        output_dir (str): 输出目录
        voice_type (str): 音色类型
    """
    try:
        # 如果提供了视频名称，查找对应的字幕文件和视频文件
        video_file = None
        if video_name:
            subtitle_file = find_english_subtitle(video_name)
            video_file = find_video_file(video_name)
            if not subtitle_file or not video_file:
                return False
        
        # 检查文件路径
        if not subtitle_file or not os.path.exists(subtitle_file):
            logging.error(f"字幕文件不存在: {subtitle_file}")
            return False

        logging.info(f"开始处理字幕文件: {subtitle_file}")
        
        # 获取视频文件夹名称
        video_folder = os.path.basename(os.path.dirname(subtitle_file))
        
        # 创建视频专属的输出目录
        video_output_dir = os.path.join(output_dir, video_folder)
        os.makedirs(video_output_dir, exist_ok=True)
        
        # 获取序列号并创建序列号子文件夹
        sequence_number = get_next_sequence_number(video_output_dir)
        sequence_dir = os.path.join(video_output_dir, sequence_number)
        os.makedirs(sequence_dir, exist_ok=True)
        
        # 创建时间戳目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_dir = os.path.join(sequence_dir, f"subtitle_{timestamp}")
        os.makedirs(analysis_dir, exist_ok=True)
        
        logging.info(f"创建输出目录结构:")
        logging.info(f"- 视频目录: {video_output_dir}")
        logging.info(f"- 序号目录: {sequence_dir}")
        logging.info(f"- 分析目录: {analysis_dir}")
        
        # 1. 分析字幕
        logging.info("开始分析字幕...")
        analyzer = SubtitleAnalyzer()
        results = analyzer.process_subtitle_file(subtitle_file)
        
        if not results:
            logging.error("字幕分析失败")
            return False
            
        # 验证时间戳
        logging.info("验证时间戳...")
        verified_results = analyzer.verify_timestamp(subtitle_file, results)
        
        # 添加视频信息到分析结果
        verified_results["video_info"] = {
            "folder": video_folder,
            "subtitle_file": os.path.basename(subtitle_file)
        }
        
        # 保存分析结果
        analysis_file = os.path.join(analysis_dir, "analysis.json")
        save_analysis_results(verified_results, analysis_file)
        logging.info(f"分析结果已保存到: {analysis_file}")
        
        # 生成中英文字幕文件路径
        en_srt = subtitle_file
        zh_srt = os.path.join(os.path.dirname(subtitle_file), f"{os.path.splitext(os.path.basename(subtitle_file))[0].replace('_en', '')}_zh.srt")
        
        # 使用 merge_subtitles 生成 ASS 字幕
        from video_synthesis.core.video_combiner import merge_subtitles
        ass_output_path = merge_subtitles(zh_srt, en_srt)
        if not ass_output_path:
            logging.error("ASS 字幕生成失败")
            return False
            
        # 复制 ASS 字幕到分析目录
        ass_filename = f"subtitle_{timestamp}.ass"
        ass_analysis_path = os.path.join(analysis_dir, ass_filename)
        import shutil
        shutil.copy2(ass_output_path, ass_analysis_path)
        logging.info(f"ASS 字幕已复制到分析目录: {ass_analysis_path}")
        
        # 2. 生成音频
        logging.info("开始生成音频...")
        converter = TTSConverter(voice_type)
        
        # 设置音频输出目录
        audio_dir = os.path.join(analysis_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)
        
        # 转换音频
        converter.convert_subtitle_items(verified_results, audio_dir)
        
        # 3. 剪辑视频
        if video_file:
            logging.info("开始剪辑视频...")
            clipper = VideoClipper(
                video_file, 
                analysis_file, 
                audio_dir,
                generate_types=["complete"]  # 指定生成所有类型的视频
            )
            clipper.output_dir = os.path.join(analysis_dir, "clips")
            generated_clips = clipper.process_clips()
            
            if generated_clips:
                logging.info(f"成功生成 {len(generated_clips)} 个视频片段")
            else:
                logging.warning("未生成任何视频片段")
        
        # 打印统计信息
        vocab_dir = os.path.join(audio_dir, "vocabulary")
        phrases_dir = os.path.join(audio_dir, "phrases")
        expressions_dir = os.path.join(audio_dir, "expressions")
        
        vocab_count = len(os.listdir(vocab_dir)) if os.path.exists(vocab_dir) else 0
        phrases_count = len(os.listdir(phrases_dir)) if os.path.exists(phrases_dir) else 0
        expressions_count = len(os.listdir(expressions_dir)) if os.path.exists(expressions_dir) else 0
        
        print("\n处理完成！统计信息:")
        print(f"词汇音频: {vocab_count//3} 个（每个词汇生成英文、中文和注释音频）")
        print(f"短语音频: {phrases_count//3} 个（每个短语生成英文、中文和注释音频）")
        print(f"表达音频: {expressions_count//3} 个（每个表达生成英文、中文和注释音频）")
        print(f"\n输出目录: {analysis_dir}")
        
        # 确保 subtitles 目录存在
        if not os.path.exists("subtitles"):
            os.makedirs("subtitles")
        
        # 确保序号目录存在
        sequence_dir_in_subtitles = os.path.join("subtitles", video_folder, sequence_number)
        os.makedirs(sequence_dir_in_subtitles, exist_ok=True)
        
        # 确保分析目录存在并复制文件
        analysis_dir_in_subtitles = os.path.join(sequence_dir_in_subtitles, f"subtitle_{timestamp}")
        if not os.path.exists(analysis_dir_in_subtitles):
            shutil.copytree(analysis_dir, analysis_dir_in_subtitles)
        
        return analysis_dir
        
    except Exception as e:
        logging.error(f"处理字幕时出错: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

def list_available_videos():
    """列出assets/pip1_videos目录下所有可用的视频"""
    videos_dir = os.path.join("assets", "pip1_videos")
    if not os.path.exists(videos_dir):
        print("视频目录不存在")
        return
        
    videos = [d for d in os.listdir(videos_dir) 
             if os.path.isdir(os.path.join(videos_dir, d)) and 
             glob.glob(os.path.join(videos_dir, d, "*_en.srt"))]
    
    if not videos:
        print("没有找到包含英文字幕的视频")
        return
        
    print("\n可用的视频列表:")
    for video in videos:
        print(f"- {video}")

def generate_ass_subtitle(analysis_results: dict, output_path: str) -> bool:
    """
    生成 ASS 格式的字幕文件
    
    Args:
        analysis_results (dict): 字幕分析结果
        output_path (str): 输出文件路径
        
    Returns:
        bool: 是否成功生成字幕文件
    """
    try:
        logging.info(f"开始生成 ASS 字幕: {output_path}")
        
        # 1. 数据验证
        if not isinstance(analysis_results, dict):
            logging.error(f"分析结果格式错误: {type(analysis_results)}")
            return False
            
        subtitle_items = analysis_results.get('subtitle_items', [])
        if not subtitle_items:
            logging.error("未找到字幕条目")
            return False
            
        logging.info(f"找到 {len(subtitle_items)} 条字幕")
        
        # 2. ASS 文件头部信息
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

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        # 3. 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 4. 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            # 写入头部信息
            f.write(ass_header)
            logging.info("已写入 ASS 头部信息")
            
            # 写入字幕内容
            for i, item in enumerate(subtitle_items, 1):
                # 数据验证
                if not all(k in item for k in ['start_time', 'end_time', 'chinese_text', 'english_text']):
                    logging.warning(f"第 {i} 条字幕数据不完整，跳过")
                    continue
                
                # 获取时间和文本
                start_time = item['start_time']
                end_time = item['end_time']
                chinese_text = item['chinese_text']
                english_text = item['english_text']
                
                # 记录每条字幕的信息（调试用）
                logging.debug(f"处理第 {i} 条字幕:")
                logging.debug(f"  开始时间: {start_time}")
                logging.debug(f"  结束时间: {end_time}")
                logging.debug(f"  中文文本: {chinese_text}")
                logging.debug(f"  英文文本: {english_text}")
                
                # 写入字幕
                f.write(f'Dialogue: 0,{start_time},{end_time},CN,,0,0,0,,{chinese_text}\n')
                f.write(f'Dialogue: 1,{start_time},{end_time},EN,,0,0,0,,{english_text}\n')
            
            logging.info(f"已写入 {len(subtitle_items)} 条字幕")
        
        # 5. 验证生成的文件
        if not os.path.exists(output_path):
            logging.error("文件未创建成功")
            return False
            
        file_size = os.path.getsize(output_path)
        if file_size == 0:
            logging.error("生成的文件为空")
            return False
            
        # 读取并验证内容
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) < len(ass_header):
                logging.error("文件内容不完整")
                return False
                
        logging.info(f"ASS 字幕文件生成成功: {output_path}")
        logging.info(f"文件大小: {file_size} 字节")
        return True
        
    except Exception as e:
        logging.error(f"生成 ASS 字幕文件时出错: {str(e)}")
        import traceback
        logging.error(f"详细错误信息:\n{traceback.format_exc()}")
        return False

def main():
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("使用方法:")
        print("python process_subtitle.py -v <视频名称> [输出目录] [音色类型]")
        print("python process_subtitle.py -s <字幕文件路径> [输出目录] [音色类型]")
        print("python process_subtitle.py -l  # 列出可用的视频")
        print("\n可用的音色类型:")
        print("- 影视解说小帅（默认）")
        print("- 标准女声")
        print("- 标准男声")
        print("- 解说小帅多情感")
        return
        
    # 处理命令行参数
    if sys.argv[1] == "-l":
        list_available_videos()
        return
        
    if sys.argv[1] == "-v":
        if len(sys.argv) < 3:
            print("请提供视频名称")
            return
        video_name = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else "subtitles"
        voice_type = sys.argv[4] if len(sys.argv) > 4 else "影视解说小帅"
        result_dir = process_subtitle(video_name=video_name, output_dir=output_dir, voice_type=voice_type)
    elif sys.argv[1] == "-s":
        if len(sys.argv) < 3:
            print("请提供字幕文件路径")
            return
        subtitle_file = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else "subtitles"
        voice_type = sys.argv[4] if len(sys.argv) > 4 else "影视解说小帅"
        result_dir = process_subtitle(subtitle_file=subtitle_file, output_dir=output_dir, voice_type=voice_type)
    else:
        print("无效的参数，请使用 -v 或 -s 选项")
        return
    
    if result_dir:
        print("\n✅ 处理成功完成！")
        print(f"输出目录: {result_dir}")
    else:
        print("\n❌ 处理过程中出现错误，请查看日志文件了解详情。")

if __name__ == "__main__":
    main() 
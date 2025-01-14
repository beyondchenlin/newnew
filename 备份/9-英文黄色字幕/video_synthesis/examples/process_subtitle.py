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
        
        # 创建输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_dir = os.path.join(output_dir, f"subtitle_{timestamp}")
        os.makedirs(analysis_dir, exist_ok=True)
        
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
            "folder": os.path.basename(os.path.dirname(subtitle_file)),
            "subtitle_file": os.path.basename(subtitle_file)
        }
        
        # 保存分析结果
        analysis_file = os.path.join(analysis_dir, "analysis.json")
        save_analysis_results(verified_results, analysis_file)
        logging.info(f"分析结果已保存到: {analysis_file}")
        
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
        
        return analysis_dir
        
    except Exception as e:
        logging.error(f"处理过程中出现错误: {str(e)}")
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
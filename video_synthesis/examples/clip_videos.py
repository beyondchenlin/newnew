"""
视频剪辑脚本：根据analysis.json中的时间戳信息剪辑视频片段并与音频合并
使用方法：python clip_videos.py
"""

import os
import sys
import glob
import json
from datetime import datetime
from typing import Optional, List, Tuple

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(current_dir)

from video_synthesis.core.video_clipper import VideoClipper

def find_latest_analysis() -> Optional[str]:
    """查找最新的分析结果文件
    Returns:
        str: JSON文件路径，如果没有找到则返回None
    """
    # 检查subtitles目录是否存在
    if not os.path.exists("subtitles"):
        print("❌ 未找到subtitles目录")
        print("💡 请先运行字幕分析程序生成分析结果")
        return None
    
    # 查找subtitles目录下的所有分析目录
    subtitle_dirs = []
    for item in os.listdir("subtitles"):
        full_path = os.path.join("subtitles", item)
        if os.path.isdir(full_path) and item.startswith("subtitle_"):
            subtitle_dirs.append(full_path)
    
    if not subtitle_dirs:
        print("❌ subtitles目录下没有任何分析目录")
        print("💡 请先运行字幕分析程序生成分析结果")
        return None
    
    # 按时间戳排序，获取最新的目录
    latest_dir = max(subtitle_dirs, key=os.path.getctime)
    print(f"📂 找到最新的分析目录: {latest_dir}")
    
    # 检查analysis.json是否存在
    json_path = os.path.join(latest_dir, "analysis.json")
    if not os.path.exists(json_path):
        print(f"❌ 未找到分析结果文件: {json_path}")
        print("💡 请确保字幕分析程序正确运行并生成了analysis.json文件")
        return None
    
    return json_path

def process_video() -> List[str]:
    """处理视频剪辑
    Returns:
        List[str]: 生成的视频片段路径列表
    """
    print("\n=== 开始处理视频剪辑 ===")
    
    # 1. 查找最新的分析结果
    json_path = find_latest_analysis()
    if not json_path:
        return []
    
    # 2. 获取分析目录和音频目录
    analysis_dir = os.path.dirname(json_path)
    audio_dir = os.path.join(analysis_dir, "audio")
    if not os.path.exists(audio_dir):
        print(f"❌ 未找到音频目录: {audio_dir}")
        print("💡 请确保已经生成了音频文件")
        return []
    
    # 3. 读取分析结果
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'video_info' not in data:
                print("❌ 分析文件中未找到视频信息")
                return []
            video_folder = data['video_info']['folder']
    except Exception as e:
        print(f"❌ 读取分析文件失败: {str(e)}")
        return []
    
    # 4. 查找视频文件
    video_dir = os.path.join("assets", "pip1_videos", video_folder)
    if not os.path.exists(video_dir):
        print(f"❌ 未找到视频目录: {video_dir}")
        return []
    
    # 查找视频文件
    video_path = None
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov']
    for file in os.listdir(video_dir):
        if any(file.lower().endswith(ext) for ext in video_extensions):
            video_path = os.path.join(video_dir, file)
            print(f"✅ 找到视频文件: {video_path}")
            break
    
    if not video_path:
        print(f"❌ 未找到视频文件")
        return []
    
    # 5. 创建输出目录
    output_dir = os.path.join(analysis_dir, "clips")
    os.makedirs(output_dir, exist_ok=True)
    
    # 6. 处理视频剪辑
    print(f"\n📽️ 开始处理视频: {os.path.basename(video_path)}")
    print(f"📊 使用分析文件: {json_path}")
    print(f"🔊 使用音频目录: {audio_dir}")
    
    clipper = VideoClipper(video_path, json_path, audio_dir)
    clipper.output_dir = output_dir
    result_clips = clipper.process_clips()
    
    if result_clips:
        print(f"\n✅ 成功生成 {len(result_clips)} 个视频片段")
        print(f"📁 输出目录: {output_dir}")
        for clip in result_clips:
            print(f"   - {os.path.basename(clip)}")
    else:
        print("\n❌ 未能生成任何视频片段")
        print("💡 可能的原因：")
        print("   1. 分析结果中没有有效的时间戳")
        print("   2. 视频文件格式不正确")
        print("   3. 音频文件不存在或格式不正确")
    
    return result_clips

def main():
    """主函数"""
    process_video()

if __name__ == "__main__":
    main() 
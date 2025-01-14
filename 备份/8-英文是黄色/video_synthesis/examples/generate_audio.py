"""
生成音频文件的示例脚本
"""

import os
import json
import logging
from datetime import datetime
from video_synthesis.core.tts_huoshan import TTSConverter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/audio_generation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

def main():
    try:
        # 读取最新的分析结果
        subtitles_dir = "subtitles"
        analysis_files = [f for f in os.listdir(subtitles_dir) if f.startswith("subtitle_analysis_verified_")]
        if not analysis_files:
            logging.error("未找到分析结果文件")
            return
            
        # 获取最新的分析文件
        latest_file = max(analysis_files, key=lambda x: x.split("_")[-1].split(".")[0])
        analysis_file = os.path.join(subtitles_dir, latest_file)
        
        logging.info(f"使用分析文件: {analysis_file}")
        
        # 读取分析结果
        with open(analysis_file, 'r', encoding='utf-8') as f:
            analysis_result = json.load(f)
            
        # 创建TTS转换器，使用影视解说小帅音色
        converter = TTSConverter("影视解说小帅")
        
        # 设置音频输出目录为subtitles目录下的audio子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join("subtitles", "audio", timestamp)
        os.makedirs(output_dir, exist_ok=True)
        
        logging.info(f"开始生成音频文件，输出目录: {output_dir}")
        
        # 转换所有内容为音频
        converter.convert_subtitle_items(analysis_result, output_dir)
        
        logging.info("音频生成完成")
        
        # 打印生成的文件数量
        vocab_dir = os.path.join(output_dir, "vocabulary")
        phrases_dir = os.path.join(output_dir, "phrases")
        expressions_dir = os.path.join(output_dir, "expressions")
        
        vocab_count = len(os.listdir(vocab_dir)) if os.path.exists(vocab_dir) else 0
        phrases_count = len(os.listdir(phrases_dir)) if os.path.exists(phrases_dir) else 0
        expressions_count = len(os.listdir(expressions_dir)) if os.path.exists(expressions_dir) else 0
        
        print("\n生成结果统计:")
        print(f"词汇音频: {vocab_count//2} 个（中英各一个）")
        print(f"短语音频: {phrases_count//2} 个（中英各一个）")
        print(f"表达音频: {expressions_count//2} 个（中英各一个）")
        
    except Exception as e:
        logging.error(f"处理过程中出现错误: {str(e)}")

if __name__ == "__main__":
    main() 
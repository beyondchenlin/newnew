"""
字幕处理模块：自动监测视频提取并处理对应字幕
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional
from .deepseek import SubtitleAnalyzer, save_analysis_results
from .tts_huoshan import TTSConverter

class SubtitleProcessor:
    """字幕处理器：自动处理视频对应的字幕"""
    
    def __init__(self, voice_type: str = "影视解说小帅"):
        """
        初始化字幕处理器
        
        Args:
            voice_type (str): TTS音色类型
        """
        self.voice_type = voice_type
        self.setup_logging()
        
    def setup_logging(self):
        """配置日志"""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        self.logger = logging.getLogger("SubtitleProcessor")
        self.logger.setLevel(logging.INFO)
        
        # 文件处理器
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fh = logging.FileHandler(
            os.path.join(log_dir, f'subtitle_process_{timestamp}.log'),
            encoding='utf-8'
        )
        fh.setLevel(logging.INFO)
        
        # 控制台处理器
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # 格式化器
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        
    def find_english_subtitle(self, video_name: str) -> Optional[str]:
        """
        查找视频对应的英文字幕文件
        
        Args:
            video_name (str): 视频名称
            
        Returns:
            Optional[str]: 字幕文件路径，如果未找到则返回None
        """
        # 构建可能的字幕文件路径
        video_dir = os.path.join("assets", "pip1_videos", video_name)
        possible_paths = [
            os.path.join(video_dir, f"{video_name}_en.srt"),  # 标准命名
            os.path.join(video_dir, "en.srt"),                # 简单命名
            os.path.join(video_dir, "subtitle_en.srt")        # 其他可能的命名
        ]
        
        # 检查所有可能的路径
        for path in possible_paths:
            if os.path.exists(path):
                self.logger.info(f"找到字幕文件: {path}")
                return path
                
        self.logger.error(f"未找到视频 {video_name} 的英文字幕文件")
        return None
        
    def process_video_subtitle(self, video_name: str, output_dir: str = "subtitles") -> bool:
        """
        处理视频对应的字幕
        
        Args:
            video_name (str): 视频名称
            output_dir (str): 输出目录
            
        Returns:
            bool: 处理是否成功
        """
        try:
            # 查找字幕文件
            subtitle_file = self.find_english_subtitle(video_name)
            if not subtitle_file:
                return False
                
            self.logger.info(f"开始处理视频 {video_name} 的字幕")
            
            # 创建输出目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            analysis_dir = os.path.join(output_dir, f"subtitle_{timestamp}")
            os.makedirs(analysis_dir, exist_ok=True)
            
            # 1. 分析字幕
            self.logger.info("开始分析字幕...")
            analyzer = SubtitleAnalyzer()
            results = analyzer.process_subtitle_file(subtitle_file)
            
            if not results:
                self.logger.error("字幕分析失败")
                return False
                
            # 验证时间戳
            self.logger.info("验证时间戳...")
            verified_results = analyzer.verify_timestamp(subtitle_file, results)
            
            # 保存分析结果
            analysis_file = os.path.join(analysis_dir, "analysis.json")
            # 添加视频文件夹信息
            verified_results["video_info"] = {
                "folder": os.path.basename(os.path.dirname(subtitle_file)),  # 获取字幕文件所在文件夹名称
                "subtitle_file": os.path.basename(subtitle_file)  # 字幕文件名
            }
            save_analysis_results(verified_results, analysis_file)
            self.logger.info(f"分析结果已保存到: {analysis_file}")
            
            # 2. 生成音频
            self.logger.info("开始生成音频...")
            converter = TTSConverter(self.voice_type)
            
            # 设置音频输出目录
            audio_dir = os.path.join(analysis_dir, "audio")
            os.makedirs(audio_dir, exist_ok=True)
            
            # 转换音频
            converter.convert_subtitle_items(verified_results, audio_dir)
            
            # 打印统计信息
            vocab_dir = os.path.join(audio_dir, "vocabulary")
            phrases_dir = os.path.join(audio_dir, "phrases")
            expressions_dir = os.path.join(audio_dir, "expressions")
            
            vocab_count = len(os.listdir(vocab_dir)) if os.path.exists(vocab_dir) else 0
            phrases_count = len(os.listdir(phrases_dir)) if os.path.exists(phrases_dir) else 0
            expressions_count = len(os.listdir(expressions_dir)) if os.path.exists(expressions_dir) else 0
            
            self.logger.info("\n处理完成！统计信息:")
            self.logger.info(f"词汇音频: {vocab_count//3} 个（每个词汇生成英文、中文和注释音频）")
            self.logger.info(f"短语音频: {phrases_count//3} 个（每个短语生成英文、中文和注释音频）")
            self.logger.info(f"表达音频: {expressions_count//3} 个（每个表达生成英文、中文和注释音频）")
            self.logger.info(f"\n输出目录: {analysis_dir}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理过程中出现错误: {str(e)}", exc_info=True)
            return False 
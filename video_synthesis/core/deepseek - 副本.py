"""
字幕分析模块 - 使用通义千问 API分析英文字幕并提取简单词汇和短语
"""

import os
import re
import json
import logging
import random
from openai import OpenAI
from typing import List, Dict, Tuple

# 通义千问 API配置
QIANWEN_API_KEY = "sk-17d366fd6a8c450e8d08313ead5f24a9"
QIANWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

class AnalysisHistory:
    """分析历史记录类"""
    
    def __init__(self, history_file="analysis_history.json"):
        """
        初始化历史记录
        
        Args:
            history_file (str): 历史记录文件路径
        """
        self.history_file = history_file
        self.history = self._load_history()
    
    def _load_history(self) -> Dict:
        """加载历史记录"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"vocabulary": set(), "phrases": set(), "expressions": set()}
        except Exception as e:
            logging.error(f"加载历史记录失败: {str(e)}")
            return {"vocabulary": set(), "phrases": set(), "expressions": set()}
    
    def _save_history(self):
        """保存历史记录"""
        try:
            # 将集合转换为列表以便JSON序列化
            history_to_save = {
                k: list(v) for k, v in self.history.items()
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存历史记录失败: {str(e)}")
    
    def is_duplicate(self, category: str, text: str) -> bool:
        """
        检查文本是否重复
        
        Args:
            category (str): 类别（vocabulary/phrases/expressions）
            text (str): 要检查的文本
            
        Returns:
            bool: 是否重复
        """
        return text.lower() in {t.lower() for t in self.history[category]}
    
    def add_item(self, category: str, text: str):
        """添加新项目到历史记录"""
        self.history[category].add(text)
        self._save_history()

class SubtitleAnalyzer:
    """字幕分析器类"""
    
    def __init__(self):
        """初始化字幕分析器"""
        self.client = OpenAI(
            api_key=QIANWEN_API_KEY,
            base_url=QIANWEN_BASE_URL
        )
        # 提取计划：指定每个类别从哪些时间段提取内容
        self.extraction_plan = {
            "vocabulary": ["segment_1", "segment_4"],
            "phrases": ["segment_2", "segment_5"],
            "expressions": ["segment_3", "segment_6"]
        }

    def parse_timestamp(self, timestamp: str) -> Tuple[int, int, int, int]:
        """
        解析时间戳字符串为小时、分钟、秒、毫秒
        
        Args:
            timestamp (str): 格式如 "00:00:03,133"
            
        Returns:
            Tuple[int, int, int, int]: (小时, 分钟, 秒, 毫秒)
        """
        time_parts = timestamp.replace(',', ':').split(':')
        return (
            int(time_parts[0]),  # 小时
            int(time_parts[1]),  # 分钟
            int(time_parts[2]),  # 秒
            int(time_parts[3])   # 毫秒
        )

    def time_to_seconds(self, time_str: str) -> float:
        """
        将时间戳转换为秒数
        
        Args:
            time_str: 时间戳字符串 (格式: HH:MM:SS,mmm)
        Returns:
            float: 秒数
        """
        h, m, s = time_str.split(':')
        s, ms = s.split(',')
        return float(h) * 3600 + float(m) * 60 + float(s) + float(ms) / 1000

    def seconds_to_time(self, seconds: float) -> str:
        """
        将秒数转换为时间戳字符串
        
        Args:
            seconds: 秒数
        Returns:
            str: 时间戳字符串 (格式: HH:MM:SS,mmm)
        """
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def process_subtitles_by_segment(self, subtitles: List[Dict]) -> Dict:
        """
        按时间段处理字幕
        
        Args:
            subtitles: 原始字幕列表
        Returns:
            Dict: 按时间段分类的字幕
        """
        # 计算视频总时长
        total_duration = max(self.time_to_seconds(s["end_time"]) for s in subtitles)
        
        # 定义时间段
        time_ranges = {
            "segment_1": (7, 15),  # 固定7-15秒
            "segment_2": (15, total_duration * 0.3),
            "segment_3": (total_duration * 0.3, total_duration * 0.5),
            "segment_4": (total_duration * 0.5, total_duration * 0.7),
            "segment_5": (total_duration * 0.7, total_duration * 0.85),
            "segment_6": (total_duration * 0.85, total_duration - 7)
        }
        
        # 初始化分段字幕
        segmented_subtitles = {segment: [] for segment in time_ranges.keys()}
        
        # 将字幕分配到对应时间段
        for subtitle in subtitles:
            start_time = self.time_to_seconds(subtitle["start_time"])
            end_time = self.time_to_seconds(subtitle["end_time"])
            
            for segment, (start, end) in time_ranges.items():
                if start <= start_time < end:
                    # 检查是否需要跳过
                    if (segment == "segment_1" and (start_time < 7 or end_time > 15)) or \
                       (end_time > (total_duration - 7)):
                        subtitle["skip_extract"] = True
                    else:
                        subtitle["skip_extract"] = False
                    segmented_subtitles[segment].append(subtitle)
                    break
        
        return segmented_subtitles

    def analyze_segment(self, segment_name: str, segment_subtitles: List[Dict], category: str) -> Dict:
        """
        分析单个时间段的字幕内容
        
        Args:
            segment_name: 时间段名称
            segment_subtitles: 该时间段的字幕列表
            category: 提取类别（vocabulary/phrases/expressions）
        Returns:
            Dict: 提取结果
        """
        prompt = f"""
        你是一位英语教学专家。现在请从给定的字幕中提取一个{category}并翻译。

        当前时间段：{segment_name}
        提取类别：{category}
        
        字幕内容：
        {json.dumps(segment_subtitles, ensure_ascii=False, indent=2)}
        
        要求：
        1. 只提取一个内容
        2. 必须从当前时间段的字幕中选择
        3. 不要选择被标记为skip_extract的内容
        4. 必须严格按照以下JSON格式返回，不要有任何其他内容：
        {{
            "segment": "{segment_name}",
            "text": "提取的内容",
            "chinese": "中文翻译",
            "notes": "词性和使用场景说明",
            "verified": true
        }}
        
        注意：
        1. 如果是vocabulary，提取单词
        2. 如果是phrases，提取2-4个词的短语
        3. 如果是expressions，提取完整句子或表达
        4. notes字段需要包含词性和使用场景的说明
        """
        
        try:
            completion = self.client.chat.completions.create(
                model="qwen-max",
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位专业的英语教学专家。你的任务是从字幕中提取内容并翻译。你必须严格按照指定的JSON格式返回结果，不要包含任何额外的解释或文本。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3
            )
            
            content = completion.choices[0].message.content
            # 添加日志，查看原始返回内容
            logging.info(f"API返回的原始内容: {content}")
            
            # 清理可能的markdown格式
            content = content.strip()
            if content.startswith("```json"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("\n", 1)[0]
            content = content.strip()
            
            # 添加日志，查看清理后的内容
            logging.info(f"清理后的内容: {content}")
            
            try:
                result = json.loads(content)
                # 验证返回的数据格式
                required_fields = ["segment", "text", "chinese", "notes", "verified"]
                if all(field in result for field in required_fields):
                    # 将 segment_X 转换为数字
                    if isinstance(result["segment"], str) and result["segment"].startswith("segment_"):
                        result["segment"] = int(result["segment"].split("_")[1])
                    return result
                else:
                    logging.error(f"返回的数据缺少必要字段: {result}")
                    return None
                    
            except json.JSONDecodeError as e:
                logging.error(f"JSON解析错误: {str(e)}")
                logging.error(f"导致错误的内容: {content}")
                return None
                
        except Exception as e:
            logging.error(f"分析时间段失败: {str(e)}")
            return None

    def extract_words_by_plan(self, segmented_subtitles: Dict) -> Dict:
        """
        按计划从各时间段提取单词
        
        Args:
            segmented_subtitles: 按时间段分类的字幕
        Returns:
            Dict: 提取结果
        """
        results = {
            "vocabulary": [],
            "phrases": [],
            "expressions": []
        }
        
        # 按计划提取
        for category, segments in self.extraction_plan.items():
            for segment in segments:
                if segment in segmented_subtitles and segmented_subtitles[segment]:
                    result = self.analyze_segment(
                        segment_name=segment,
                        segment_subtitles=segmented_subtitles[segment],
                        category=category
                    )
                    if result:
                        results[category].append(result)
        
        return results

    def validate_results(self, results: Dict) -> bool:
        """
        验证处理结果
        
        Args:
            results: 处理结果
        Returns:
            bool: 是否有效
        """
        try:
            # 检查必要的类别
            required_categories = ["vocabulary", "phrases", "expressions"]
            if not all(category in results for category in required_categories):
                logging.error("缺少必要的类别")
                return False
                
            # 检查每个类别的数量
            if not all(len(results[category]) == 2 for category in required_categories):
                logging.error("每个类别必须包含两个项目")
                return False
                
            # 检查每个项目的必要字段
            required_fields = ["segment", "text", "chinese", "notes", "verified"]
            for category in required_categories:
                for item in results[category]:
                    if not all(field in item for field in required_fields):
                        logging.error(f"项目缺少必要字段: {item}")
                        return False
                    
                    # 检查segment是否为数字
                    if not isinstance(item["segment"], int):
                        logging.error(f"segment必须为数字: {item}")
                        return False
                    
                    # 检查verified是否为布尔值
                    if not isinstance(item["verified"], bool):
                        logging.error(f"verified必须为布尔值: {item}")
                        return False
                    
            return True
            
        except Exception as e:
            logging.error(f"验证结果失败: {str(e)}")
            return False

    def process_subtitle_file(self, file_path: str) -> Dict:
        """
        处理字幕文件的主函数
        
        Args:
            file_path: 字幕文件路径
        Returns:
            Dict: 处理结果
        """
        try:
            # 1. 读取字幕文件
            subtitles = self.read_srt_file(file_path)
            
            # 2. 按时间段分割字幕
            segmented_subtitles = self.process_subtitles_by_segment(subtitles)
            
            # 3. 按计划提取单词
            results = self.extract_words_by_plan(segmented_subtitles)
            
            # 4. 验证结果
            if not self.validate_results(results):
                logging.error("结果验证失败")
                return None
            
            return results
            
        except Exception as e:
            logging.error(f"处理字幕文件失败: {str(e)}")
            return None

    def read_srt_file(self, file_path: str) -> List[Dict]:
        """
        读取.srt字幕文件，保留时间戳信息
        
        Args:
            file_path (str): 字幕文件路径
            
        Returns:
            List[Dict]: 字幕内容列表，每项包含文本和时间戳
        """
        subtitles = []
        current_subtitle = {}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 序号行
            if line.isdigit():
                if current_subtitle:
                    subtitles.append(current_subtitle)
                current_subtitle = {"index": int(line)}
                i += 1
                continue
                
            # 时间戳行
            if '-->' in line:
                timestamps = line.split(' --> ')
                current_subtitle["start_time"] = timestamps[0].strip()
                current_subtitle["end_time"] = timestamps[1].strip()
                current_subtitle["text"] = ""
                i += 1
                continue
                
            # 文本行
            if line and current_subtitle:
                if current_subtitle["text"]:
                    current_subtitle["text"] += " " + line
                else:
                    current_subtitle["text"] = line
            i += 1
            
        # 添加最后一个字幕
        if current_subtitle:
            subtitles.append(current_subtitle)
            
        return subtitles

    def verify_timestamp(self, srt_file: str, analysis_result: Dict) -> Dict:
        """验证时间戳并返回验证后的结果
        
        Args:
            srt_file: 字幕文件路径
            analysis_result: 分析结果
            
        Returns:
            Dict: 验证后的结果
        """
        def is_within_7_15_seconds(time_str: str) -> bool:
            """检查时间是否在7-15秒范围内"""
            h, m, s = time_str.split(':')
            s, ms = s.split(',')
            total_seconds = float(h) * 3600 + float(m) * 60 + float(s) + float(ms) / 1000
            return 7.0 <= total_seconds <= 15.0

        verification_result = {
            "vocabulary": [],
            "phrases": [],
            "expressions": []
        }
        
        try:
            # 读取原始字幕
            subtitles = self.read_srt_file(srt_file)
            
            # 创建时间段映射
            segment_map = {}
            for subtitle in subtitles:
                text = subtitle["text"].lower()
                segment_map[text] = {
                    "start_time": subtitle["start_time"],
                    "end_time": subtitle["end_time"],
                    "full_text": subtitle["text"]
                }
            
            # 验证每个类别
            for category in ["vocabulary", "phrases", "expressions"]:
                for item in analysis_result[category]:
                    text = item["text"].lower()
                    segment = item["segment"]
                    
                    # 在原始字幕中查找匹配的文本
                    found = False
                    for subtitle_text, time_info in segment_map.items():
                        if text in subtitle_text.lower().split():
                            item["verified"] = True
                            item["start_time"] = time_info["start_time"]
                            item["end_time"] = time_info["end_time"]
                            item["original_subtitle"] = time_info["full_text"]
                            found = True
                            break
                    
                    if not found:
                        item["verified"] = False
                        item["error"] = "未找到匹配的字幕文本"
                    
                    # 检查第一段的时间限制
                    if segment == 1 and found:  # 注意这里使用数字1而不是"segment_1"
                        if not is_within_7_15_seconds(item["start_time"]):
                            item["verified"] = False
                            item["error"] = "第一段内容必须在7-15秒范围内"
                    
                    verification_result[category].append(item)
            
            return verification_result
            
        except Exception as e:
            logging.error(f"验证时间戳失败: {str(e)}")
            return analysis_result

def save_analysis_results(results: Dict, output_file: str):
    """
    保存分析结果到JSON文件
    
    Args:
        results (Dict): 分析结果
        output_file (str): 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

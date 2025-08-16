"""
字幕分析模块 - 使用DeepSeek API分析英文字幕并提取简单词汇和短语
"""

import os
import re
import json
import requests
from typing import List, Dict, Tuple
import logging
import random

# DeepSeek API配置
DEEPSEEK_API_KEY = "sk-0dc540bed82a46e2b66b72999b8db6d0"

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
        self.api_key = DEEPSEEK_API_KEY
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
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
    
    def find_timestamp_for_text(self, subtitles: List[Dict], target_text: str) -> Dict:
        """
        在字幕列表中查找包含目标文本的时间戳
        
        Args:
            subtitles (List[Dict]): 字幕列表
            target_text (str): 要查找的文本
            
        Returns:
            Dict: 包含时间戳的字典，如果未找到则返回None
        """
        target_text = target_text.lower()
        for subtitle in subtitles:
            if target_text in subtitle["text"].lower():
                return {
                    "text": target_text,
                    "start_time": subtitle["start_time"],
                    "end_time": subtitle["end_time"],
                    "full_context": subtitle["text"]
                }
        return None
    
    def analyze_subtitles(self, subtitles: List[Dict]) -> Dict:
        """分析字幕内容并提取关键信息"""
        # 直接执行分析，不做重复检查
        results = self._perform_analysis(subtitles)
        return results
    
    def _perform_analysis(self, subtitles: List[Dict]) -> Dict:
        """执行实际的分析操作（原来analyze_subtitles的主要逻辑）"""
        def time_to_seconds(time_str: str) -> float:
            h, m, s = time_str.split(':')
            s, ms = s.split(',')
            return float(h) * 3600 + float(m) * 60 + float(s) + float(ms) / 1000
            
        def seconds_to_time(seconds: float) -> str:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        # 计算视频总时长
        total_duration = max(time_to_seconds(s["end_time"]) for s in subtitles)
        
        # 创建时间段划分
        time_ranges = {
            "segment_1": (7, 15),  # 第一段固定为7-15秒
            "segment_2": (15, total_duration * 0.3),
            "segment_3": (total_duration * 0.3, total_duration * 0.5),
            "segment_4": (total_duration * 0.5, total_duration * 0.7),
            "segment_5": (total_duration * 0.7, total_duration * 0.85),
            "segment_6": (total_duration * 0.85, total_duration - 7)  # 排除最后7秒
        }
        
        # 初始化分段字幕
        segmented_subtitles = {f"segment_{i}": [] for i in range(1, 7)}
        
        # 将字幕按时间段分类
        for subtitle in subtitles:
            start = time_to_seconds(subtitle["start_time"])
            end = time_to_seconds(subtitle["end_time"])
            
            # 将字幕分配到对应时间段
            for segment_name, (range_start, range_end) in time_ranges.items():
                if range_start <= start < range_end:
                    # 标记是否在有效时间范围内
                    if segment_name == "segment_1" and (start < 7 or end > 15):
                        subtitle["skip_extract"] = True
                    elif end > (total_duration - 7):
                        subtitle["skip_extract"] = True
                    else:
                        subtitle["skip_extract"] = False
                    segmented_subtitles[segment_name].append(subtitle)
                    break
        
        # 构建时间区间信息
        time_info = {
            name: f"{seconds_to_time(start)} - {seconds_to_time(end)}"
            for name, (start, end) in time_ranges.items()
        }
        
        # 随机分配时间段
        available_segments = list(range(1, 7))  # [1,2,3,4,5,6]
        random.shuffle(available_segments)  # 随机打乱顺序
        
        # 为每个类别分配两个时间段
        segment_assignments = {
            "vocabulary": [f"segment_{available_segments[0]}", f"segment_{available_segments[1]}"],
            "phrases": [f"segment_{available_segments[2]}", f"segment_{available_segments[3]}"],
            "expressions": [f"segment_{available_segments[4]}", f"segment_{available_segments[5]}"]
        }
        
        # 系统角色设定
        system_prompt = """
        # 角色定位：你是一位专业的英语教师，专门帮助学习者分析文本
        You are an expert English language teacher specializing in analyzing text for language learners.
        
        # 输出格式要求：
        你必须严格按照以下 JSON 格式返回结果：
        {
            "vocabulary": [
                {
                    "segment": "segment_X",
                    "text": "单词",
                    "translation": "翻译"
                },
                {
                    "segment": "segment_Y",
                    "text": "单词",
                    "translation": "翻译"
                }
            ],
            "phrases": [
                {
                    "segment": "segment_X",
                    "text": "短语",
                    "translation": "翻译"
                },
                {
                    "segment": "segment_Y",
                    "text": "短语",
                    "translation": "翻译"
                }
            ],
            "expressions": [
                {
                    "segment": "segment_X",
                    "text": "表达",
                    "translation": "翻译"
                },
                {
                    "segment": "segment_Y",
                    "text": "表达",
                    "translation": "翻译"
                }
            ]
        }
        
        # 关键规则：
        1. 必须返回有效的 JSON 格式
        2. 所有字段都必须包含
        3. 不要添加任何额外的解释或文本
        4. 每个时间段提取一个内容
        5. 确保每个时间段的内容不重复
        """

        # 用户具体要求
        user_prompt = f"""
        视频已被分为6个时间段，每个时间段的字幕内容如下。
        请从每个时间段中提取一个内容：

        第1段 (0:00:07,000 - 0:00:15,000):
        {' '.join([s["text"] + f" [{'跳过' if s.get('skip_extract', False) else '可用'}]" for s in segmented_subtitles["segment_1"]])}

        第2段 ({time_info['segment_2']}):
        {' '.join([s["text"] + f" [{'跳过' if s.get('skip_extract', False) else '可用'}]" for s in segmented_subtitles["segment_2"]])}

        第3段 ({time_info['segment_3']}):
        {' '.join([s["text"] + f" [{'跳过' if s.get('skip_extract', False) else '可用'}]" for s in segmented_subtitles["segment_3"]])}

        第4段 ({time_info['segment_4']}):
        {' '.join([s["text"] + f" [{'跳过' if s.get('skip_extract', False) else '可用'}]" for s in segmented_subtitles["segment_4"]])}

        第5段 ({time_info['segment_5']}):
        {' '.join([s["text"] + f" [{'跳过' if s.get('skip_extract', False) else '可用'}]" for s in segmented_subtitles["segment_5"]])}

        第6段 ({time_info['segment_6']}):
        {' '.join([s["text"] + f" [{'跳过' if s.get('skip_extract', False) else '可用'}]" for s in segmented_subtitles["segment_6"]])}

        提取要求：
        1. 从每个时间段中提取一个内容，可以是：
           - 单词 (vocabulary)
           - 短语 (2-4个词的短语)
           - 表达 (完整句子或表达)

        2. 内容提取规则：
           - 如果选择第1段内容，必须确保在7-15秒范围内
           - 如果内容标记为"跳过"，必须从该时间段的其他可用内容中选择
           - 字幕中的任何内容都可以被提取，不考虑难度或类型
           - 如果选择短语，必须是2-4个词的组合

        3. 输出格式要求：
           - 每个时间段提取的内容必须按类型（vocabulary/phrases/expressions）分类
           - 每个内容必须包含segment、text和translation字段
           - 每个类别（vocabulary/phrases/expressions）中的内容必须来自不同的时间段

        注意：
        1. 返回的 JSON 必须严格按照指定的格式
        2. 所选内容必须完全匹配字幕文本
        3. 确保选择的内容在对应的时间段内
        4. 如果某个内容标记为"跳过"，必须从该时间段的其他可用内容中选择
        5. 内容提取不受难度和类型限制，只要是字幕中出现的英文内容都可以选择
        6. 每个时间段提取的内容类型可以不同（可以是单词、短语或表达）
        """
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            logging.debug(f"API Response: {response.text}")
            
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                logging.debug(f"API 返回的原始内容: {content}")
                
                # 清理 Markdown 代码块标记
                content = content.strip()
                if content.startswith("```"):
                    # 移除开头的 ```json 或 ``` 标记
                    content = content.split("\n", 1)[1]
                if content.endswith("```"):
                    # 移除结尾的 ``` 标记
                    content = content.rsplit("\n", 1)[0]
                content = content.strip()
                
                try:
                    # 尝试解析返回的内容为 JSON
                    content_json = json.loads(content)
                    logging.debug(f"解析后的 JSON: {json.dumps(content_json, ensure_ascii=False, indent=2)}")
                    return content_json
                except json.JSONDecodeError as e:
                    logging.error(f"JSON 解析错误: {str(e)}")
                    logging.error(f"导致错误的内容: {content}")
                    return None
            
        except Exception as e:
            logging.error(f"发生错误: {str(e)}")
            return None
            
    def translate_items(self, items: List[Dict]) -> List[Dict]:
        """
        翻译提取的内容
        
        Args:
            items: 需要翻译的项目列表
            
        Returns:
            List[Dict]: 添加了翻译的项目列表
        """
        # 构建翻译提示词
        texts_to_translate = [item["text"] for item in items]
        translation_prompt = f"""
        请将以下英文内容翻译成中文，保持简洁准确。
        同时给出词性和使用场景的说明。
        
        英文内容：
        {json.dumps(texts_to_translate, ensure_ascii=False, indent=2)}
        
        请按以下JSON格式返回：
        {{
            "translations": [
                {{
                    "english": "原文",
                    "chinese": "中文翻译",
                    "notes": "词性和使用场景说明"
                }}
            ]
        }}
        """
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位专业的英语翻译专家，擅长准确简洁的翻译。"
                },
                {
                    "role": "user",
                    "content": translation_prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"}
        }
        
        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()
            
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                if isinstance(content, str):
                    translations = json.loads(content)
                else:
                    translations = content
                
                # 将翻译添加到原始项目中
                translation_dict = {t["english"]: t for t in translations["translations"]}
                for item in items:
                    if item["text"] in translation_dict:
                        trans = translation_dict[item["text"]]
                        item["chinese"] = trans["chinese"]
                        item["notes"] = trans["notes"]
                
            return items
            
        except Exception as e:
            logging.error(f"翻译过程中出现错误: {str(e)}")
            return items

    def process_subtitle_file(self, file_path: str) -> Dict:
        """
        处理字幕文件并返回分析结果
        
        Args:
            file_path (str): 字幕文件路径
            
        Returns:
            Dict: 分析结果
        """
        subtitles = self.read_srt_file(file_path)
        results = self.analyze_subtitles(subtitles)
        
        if results:
            # 为每个类别添加翻译
            results["vocabulary"] = self.translate_items(results["vocabulary"])
            results["phrases"] = self.translate_items(results["phrases"])
            results["expressions"] = self.translate_items(results["expressions"])
            
        return results
        
    def verify_timestamp(self, srt_file: str, analysis_result: Dict) -> Dict:
        """验证时间戳"""
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
            for item in analysis_result.get(category, []):
                text = item["text"].lower()
                segment = item["segment"]
                
                # 在原始字幕中查找匹配的文本
                found = False
                for subtitle_text, time_info in segment_map.items():
                    if text in subtitle_text:
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
                if segment == "segment_1" and found:
                    if not is_within_7_15_seconds(item["start_time"]):
                        item["verified"] = False
                        item["error"] = "第一段内容必须在7-15秒范围内"
                
                verification_result[category].append(item)
        
        return verification_result

def save_analysis_results(results: Dict, output_file: str):
    """
    保存分析结果到JSON文件
    
    Args:
        results (Dict): 分析结果
        output_file (str): 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

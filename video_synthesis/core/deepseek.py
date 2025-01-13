"""
字幕分析模块 - 使用DeepSeek API分析英文字幕并提取简单词汇和短语
"""

import os
import re
import json
import requests
from typing import List, Dict, Tuple
import logging

# DeepSeek API配置
DEEPSEEK_API_KEY = "sk-18239f30654844eeba026f9373fc1f81"

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
        """
        使用DeepSeek API分析字幕内容
        
        Args:
            subtitles (List[Dict]): 字幕内容列表
            
        Returns:
            Dict: 分析结果
        """
        # 合并所有字幕文本
        subtitle_text = " ".join([s["text"] for s in subtitles])
        
        # 系统角色设定
        system_prompt = """
        # 角色定位：你是一位专业的英语教师，专门帮助学习者分析文本
        You are an expert English language teacher specializing in analyzing text for language learners.
        
        # 主要任务：从文本中提取最有价值的语言要素，每类仅提取4个
        Your task is to extract the most valuable language elements (exactly 4 items for each category).
        
        # 输出要求：始终以JSON格式返回分析结果，每个类别必须正好包含4个项目
        Always return your analysis in valid JSON format with exactly 4 items in each category.
        """

        # 用户具体要求
        user_prompt = f"""
        请分析以下英文字幕文本，从中提取最有价值的内容（每类正好4个）：

        1. 词汇部分 (A1-B1级别) - 提取4个最有价值的词:
           - 只选择最常用、最有价值的日常词汇
           - 选择对初学者最有帮助的词
           - 确保词汇简单易懂
           - 优先选择在文本中频繁出现的词

        2. 实用短语 - 提取4个最实用的短语:
           - 选择最实用的2-4个词的短语
           - 优先选择日常对话中常用的组合
           - 确保短语容易理解和记忆
           - 选择最自然的表达方式

        3. 完整表达 - 提取4个最有用的表达:
           - 选择最实用的完整句子
           - 优先选择日常交际中常用的表达
           - 确保表达自然且实用
           - 适合初学者学习和模仿

        待分析文本: {subtitle_text}

        请只返回如下JSON格式的结果，每个类别必须正好包含4个项目:
        {{
            "vocabulary": ["词1", "词2", "词3", "词4"],
            "phrases": ["短语1", "短语2", "短语3", "短语4"],
            "expressions": ["表达1", "表达2", "表达3", "表达4"]
        }}
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
            "temperature": 0.3,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"}
        }
        
        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            logging.debug(f"API Response: {response.text}")
            
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                if isinstance(content, str):
                    content = json.loads(content)
                elif isinstance(content, dict):
                    content = content
                
                # 为每个提取的项目查找时间戳
                timestamped_result = {
                    "vocabulary": [],
                    "phrases": [],
                    "expressions": []
                }
                
                # 处理词汇
                for word in content.get("vocabulary", []):
                    timestamp = self.find_timestamp_for_text(subtitles, word)
                    if timestamp:
                        timestamped_result["vocabulary"].append(timestamp)
                
                # 处理短语
                for phrase in content.get("phrases", []):
                    timestamp = self.find_timestamp_for_text(subtitles, phrase)
                    if timestamp:
                        timestamped_result["phrases"].append(timestamp)
                
                # 处理表达
                for expression in content.get("expressions", []):
                    timestamp = self.find_timestamp_for_text(subtitles, expression)
                    if timestamp:
                        timestamped_result["expressions"].append(timestamp)
                
                return timestamped_result
            
            logging.error(f"API返回了意外的响应格式: {result}")
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
        """
        验证提取的时间戳是否准确
        
        Args:
            srt_file (str): 原始字幕文件路径
            analysis_result (Dict): 分析结果
            
        Returns:
            Dict: 验证结果
        """
        # 读取原始字幕文件
        with open(srt_file, 'r', encoding='utf-8') as f:
            original_content = f.read()
            
        verification_result = {
            "vocabulary": [],
            "phrases": [],
            "expressions": []
        }
        
        # 验证词汇
        for item in analysis_result.get("vocabulary", []):
            text = item["text"]
            start_time = item["start_time"]
            end_time = item["end_time"]
            
            # 在原始字幕中查找
            timestamp_pattern = f"{start_time} --> {end_time}"
            if timestamp_pattern in original_content:
                # 找到对应的字幕块
                subtitle_block = self._find_subtitle_block(original_content, timestamp_pattern)
                if subtitle_block and text.lower() in subtitle_block.lower():
                    item["verified"] = True
                    item["original_subtitle"] = subtitle_block.strip()
                else:
                    item["verified"] = False
                    item["error"] = "时间戳匹配但文本不匹配"
            else:
                item["verified"] = False
                item["error"] = "时间戳不匹配"
            verification_result["vocabulary"].append(item)
            
        # 验证短语
        for item in analysis_result.get("phrases", []):
            text = item["text"]
            start_time = item["start_time"]
            end_time = item["end_time"]
            
            timestamp_pattern = f"{start_time} --> {end_time}"
            if timestamp_pattern in original_content:
                subtitle_block = self._find_subtitle_block(original_content, timestamp_pattern)
                if subtitle_block and text.lower() in subtitle_block.lower():
                    item["verified"] = True
                    item["original_subtitle"] = subtitle_block.strip()
                else:
                    item["verified"] = False
                    item["error"] = "时间戳匹配但文本不匹配"
            else:
                item["verified"] = False
                item["error"] = "时间戳不匹配"
            verification_result["phrases"].append(item)
            
        # 验证表达
        for item in analysis_result.get("expressions", []):
            text = item["text"]
            start_time = item["start_time"]
            end_time = item["end_time"]
            
            timestamp_pattern = f"{start_time} --> {end_time}"
            if timestamp_pattern in original_content:
                subtitle_block = self._find_subtitle_block(original_content, timestamp_pattern)
                if subtitle_block and text.lower() in subtitle_block.lower():
                    item["verified"] = True
                    item["original_subtitle"] = subtitle_block.strip()
                else:
                    item["verified"] = False
                    item["error"] = "时间戳匹配但文本不匹配"
            else:
                item["verified"] = False
                item["error"] = "时间戳不匹配"
            verification_result["expressions"].append(item)
            
        return verification_result
    
    def _find_subtitle_block(self, content: str, timestamp: str) -> str:
        """
        在字幕内容中查找指定时间戳对应的字幕块
        
        Args:
            content (str): 字幕文件内容
            timestamp (str): 时间戳
            
        Returns:
            str: 字幕块文本
        """
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if timestamp in line and i + 1 < len(lines):
                # 收集时间戳后的所有文本行，直到遇到空行
                text_lines = []
                j = i + 1
                while j < len(lines) and lines[j].strip():
                    text_lines.append(lines[j].strip())
                    j += 1
                return ' '.join(text_lines)
        return ""

def save_analysis_results(results: Dict, output_file: str):
    """
    保存分析结果到JSON文件
    
    Args:
        results (Dict): 分析结果
        output_file (str): 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

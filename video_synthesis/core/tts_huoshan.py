#coding=utf-8

'''
requires Python 3.6 or later
pip install requests
'''
import base64
import json
import uuid
import os
import logging
import requests
from typing import Dict, List
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 火山引擎配置
appid = "4824282690"
access_token = "4nv7WXFZ2RmDhOkntKIOCntlXk-BLUc4"
cluster = "volcano_tts"
host = "openspeech.bytedance.com"
api_url = f"https://{host}/api/v1/tts"

# 声音类型映射
VOICE_TYPES = {
    "标准女声": "BV001_streaming",
    "标准男声": "BV002_streaming",
    "影视解说小帅": "BV411_streaming",
    "解说小帅多情感": "BV437_streaming"
}

class TTSConverter:
    """火山引擎TTS转换器"""
    
    def __init__(self, voice_type="影视解说小帅"):
        """
        初始化TTS转换器
        
        Args:
            voice_type (str): 声音类型，默认为影视解说小帅
        """
        self.voice_type = VOICE_TYPES.get(voice_type, "BV411_streaming")
        self.header = {
            "Authorization": f"Bearer;{access_token}",  # 注意这里使用分号
            "Content-Type": "application/json"
        }
        logging.info(f"TTS转换器初始化完成，使用声音类型: {voice_type}")
        
    def _get_request_json(self, text: str, emotion: str = None, pitch: int = 0, rate: int = 0, volume: int = 0) -> Dict:
        """
        生成请求JSON
        
        Args:
            text (str): 要转换的文本
            emotion (str, optional): 情感类型，仅在使用多情感音色时有效
            pitch (int): 音调调整，范围 -100 到 100
            rate (int): 语速调整，范围 -100 到 100
            volume (int): 音量调整，范围 -100 到 100
            
        Returns:
            Dict: 请求JSON
        """
        # 转换参数范围
        pitch_ratio = max(0.1, min(3.0, 1.0 + (float(pitch) / 100)))
        speed_ratio = max(0.2, min(3.0, 1.0 + (float(rate) / 100)))
        volume_ratio = max(0.1, min(3.0, 1.0 + (float(volume) / 100)))
        
        request_json = {
            "app": {
                "appid": appid,
                "token": access_token,
                "cluster": cluster
            },
            "user": {
                "uid": str(uuid.uuid4())
            },
            "audio": {
                "voice_type": self.voice_type,
                "encoding": "mp3",
                "speed_ratio": speed_ratio,
                "volume_ratio": volume_ratio,
                "pitch_ratio": pitch_ratio
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "text_type": "plain",
                "operation": "query"
            }
        }
        
        # 如果使用多情感音色且指定了情感，添加情感参数
        if self.voice_type == "BV437_streaming" and emotion:
            request_json["audio"]["emotion"] = emotion
            
        return request_json
        
    def convert_to_audio(self, text: str, output_path: str, emotion: str = None, 
                        pitch: int = 0, rate: int = 0, volume: int = 0) -> bool:
        """
        将文本转换为音频
        
        Args:
            text (str): 要转换的文本
            output_path (str): 输出音频文件路径
            emotion (str, optional): 情感类型
            pitch (int): 音调调整，范围 -100 到 100
            rate (int): 语速调整，范围 -100 到 100
            volume (int): 音量调整，范围 -100 到 100
            
        Returns:
            bool: 转换是否成功
        """
        try:
            logging.info(f"开始转换文本: {text}")
            request_json = self._get_request_json(text, emotion, pitch, rate, volume)
            logging.debug(f"请求JSON: {json.dumps(request_json, ensure_ascii=False, indent=2)}")
            
            resp = requests.post(api_url, json=request_json, headers=self.header)
            logging.debug(f"API响应状态码: {resp.status_code}")
            
            if resp.status_code != 200:
                logging.error(f"API请求失败: {resp.text}")
                return False
                
            result = resp.json()
            logging.debug(f"API响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
            if "data" in result:
                data = result["data"]
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(data))
                logging.info(f"音频文件已保存: {output_path}")
                return True
            else:
                logging.error(f"API响应中没有音频数据: {result}")
                return False
            
        except Exception as e:
            logging.error(f"转换失败: {str(e)}", exc_info=True)
            return False
            
    def _clean_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename (str): 原始文件名
            
        Returns:
            str: 清理后的文件名
        """
        # 替换问号和其他非法字符
        cleaned = re.sub(r'[\\/:*?"<>|]', '', filename)
        # 移除前后的点和空格
        cleaned = cleaned.strip('. ')
        # 确保文件名不为空
        if not cleaned:
            cleaned = 'unnamed'
        return cleaned

    def convert_subtitle_items(self, analysis_result: Dict, output_dir: str):
        """
        转换字幕分析结果中的所有项目
        
        Args:
            analysis_result (Dict): 字幕分析结果
            output_dir (str): 输出目录
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        logging.info(f"开始处理分析结果，输出目录: {output_dir}")
        
        # 转换词汇
        vocab_dir = os.path.join(output_dir, "vocabulary")
        os.makedirs(vocab_dir, exist_ok=True)
        logging.info("开始处理词汇...")
        for item in analysis_result.get("vocabulary", []):
            # 英文版本 (text)
            if "text" in item:
                en_filename = f"{self._clean_filename(item['text'].replace(' ', '_'))}_en.mp3"
                if self.convert_to_audio(
                    item['text'],
                    os.path.join(vocab_dir, en_filename)
                ):
                    logging.info(f"成功生成英文词汇音频: {en_filename}")
            
            # 中文版本 (chinese)
            if "chinese" in item:
                zh_filename = f"{self._clean_filename(item['text'].replace(' ', '_'))}_zh.mp3"
                if self.convert_to_audio(
                    item['chinese'],
                    os.path.join(vocab_dir, zh_filename)
                ):
                    logging.info(f"成功生成中文词汇音频: {zh_filename}")
            
            # 注释版本 (notes)
            if "notes" in item and item["notes"]:
                notes_filename = f"{self._clean_filename(item['text'].replace(' ', '_'))}_notes.mp3"
                if self.convert_to_audio(
                    item['notes'],
                    os.path.join(vocab_dir, notes_filename)
                ):
                    logging.info(f"成功生成词汇注释音频: {notes_filename}")
                
        # 转换短语和表达
        for category in ["phrases", "expressions"]:
            category_dir = os.path.join(output_dir, category)
            os.makedirs(category_dir, exist_ok=True)
            logging.info(f"开始处理{category}...")
            for item in analysis_result.get(category, []):
                # 英文版本 (text)
                if "text" in item:
                    en_filename = f"{self._clean_filename(item['text'].replace(' ', '_'))}_en.mp3"
                    if self.convert_to_audio(
                        item['text'],
                        os.path.join(category_dir, en_filename)
                    ):
                        logging.info(f"成功生成英文{category}音频: {en_filename}")
                
                # 中文版本 (chinese)
                if "chinese" in item:
                    zh_filename = f"{self._clean_filename(item['text'].replace(' ', '_'))}_zh.mp3"
                    if self.convert_to_audio(
                        item['chinese'],
                        os.path.join(category_dir, zh_filename)
                    ):
                        logging.info(f"成功生成中文{category}音频: {zh_filename}")
                
                # 注释版本 (notes)
                if "notes" in item and item["notes"]:
                    notes_filename = f"{self._clean_filename(item['text'].replace(' ', '_'))}_notes.mp3"
                    if self.convert_to_audio(
                        item['notes'],
                        os.path.join(category_dir, notes_filename)
                    ):
                        logging.info(f"成功生成{category}注释音频: {notes_filename}")
        
        logging.info("所有音频生成完成")

if __name__ == '__main__':
    # 测试代码
    converter = TTSConverter("标准女声")
    test_text = "你好，这是一个测试。"
    output_path = "test_output.mp3"
    
    # 测试基本转换
    success = converter.convert_to_audio(test_text, output_path)
    print(f"基本转换{'成功' if success else '失败'}")
    
    # 测试多情感转换
    emotion_converter = TTSConverter("解说小帅多情感")
    emotion_output = "test_output_emotion.mp3"
    success = emotion_converter.convert_to_audio(
        test_text,
        emotion_output,
        emotion="happy",
        pitch=10,
        rate=0,
        volume=0
    )
    print(f"情感转换{'成功' if success else '失败'}")

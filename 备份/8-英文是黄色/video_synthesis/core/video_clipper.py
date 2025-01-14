"""
视频剪辑核心模块：根据时间戳信息剪辑视频片段并与音频合并
"""

import os
import json
import re
import subprocess
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

class VideoTypes:
    """视频类型常量"""
    EN = "en"
    ZH = "zh"
    NOTES = "notes"
    COMPLETE = "complete"

class VideoClipper:
    """视频剪辑器"""
    
    def __init__(self, video_path: str, json_path: str, audio_dir: str, generate_types: List[str] = None):
        """初始化视频剪辑器
        Args:
            video_path: 视频文件路径
            json_path: 分析结果JSON文件路径
            audio_dir: 音频文件目录
            generate_types: 需要生成的视频类型列表，默认只生成complete版本
        """
        self.video_path = video_path
        self.json_path = json_path
        self.audio_dir = audio_dir
        self.output_dir = "output/clips"  # 默认输出目录
        
        # 设置需要生成的视频类型
        self.generate_types = generate_types if generate_types is not None else [VideoTypes.COMPLETE]
        
        # 配置日志
        self.logger = self._setup_logger()
        
        # 记录配置信息
        self.logger.info(f"视频生成类型: {self.generate_types}")
        
    def _setup_logger(self):
        """配置日志记录器"""
        # 创建logs目录
        os.makedirs("logs", exist_ok=True)
        
        # 创建日志记录器
        logger = logging.getLogger(f"VideoClipper_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        logger.setLevel(logging.DEBUG)
        
        # 创建文件处理器
        log_file = f"logs/video_clipper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建格式化器
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        logger.info(f"日志文件创建成功: {log_file}")
        logger.info(f"初始化视频剪辑器:")
        logger.info(f"- 视频文件: {self.video_path}")
        logger.info(f"- 分析文件: {self.json_path}")
        logger.info(f"- 音频目录: {self.audio_dir}")
        
        return logger
        
    def _clean_filename(self, filename: str) -> str:
        """清理文件名，移除或替换非法字符
        Args:
            filename: 原始文件名
        Returns:
            str: 清理后的文件名
        """
        # 1. 替换问号和感叹号为下划线
        filename = re.sub(r'[?!]', '_', filename)
        
        # 2. 替换空格为下划线
        filename = filename.replace(' ', '_')
        
        # 3. 移除其他非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # 4. 确保文件名不为空
        if not filename:
            filename = "unnamed"
            
        return filename
        
    def _load_analysis(self) -> Dict[str, Any]:
        """加载分析结果
        Returns:
            Dict: 分析结果数据
        """
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 读取分析文件失败: {str(e)}")
            return {}
            
    def _get_audio_paths(self, item_type: str, item_id: str) -> Dict[str, str]:
        """获取音频文件路径
        Args:
            item_type: 项目类型（vocabulary/phrases/expressions）
            item_id: 项目ID
        Returns:
            Dict[str, str]: 音频文件路径字典，键为类型（en/zh/notes），值为路径
        """
        # 1. 移除末尾的问号
        clean_id = item_id.rstrip('?')
        # 2. 替换空格为下划线
        clean_id = clean_id.replace(' ', '_')
        # 3. 移除其他非法字符
        clean_id = re.sub(r'[<>:"/\\|?*]', '', clean_id)
        
        base_path = os.path.join(self.audio_dir, item_type, clean_id)
        
        paths = {}
        for audio_type in ['en', 'zh', 'notes']:
            path = f"{base_path}_{audio_type}.mp3"
            if os.path.exists(path):
                paths[audio_type] = path
                print(f"✅ 找到音频文件: {path}")
            else:
                print(f"❌ 未找到音频文件: {path}")
                
        return paths
        
    def _parse_timestamp(self, timestamp: str) -> float:
        """解析时间戳字符串为秒数
        Args:
            timestamp: 格式如 "00:00:03,133"
        Returns:
            float: 秒数
        """
        try:
            # 分离时分秒和毫秒
            main_part, ms_part = timestamp.split(',')
            h, m, s = main_part.split(':')
            
            # 转换为秒
            total_seconds = int(h) * 3600 + int(m) * 60 + int(s)
            total_seconds += int(ms_part) / 1000
            
            return total_seconds
        except Exception as e:
            print(f"❌ 解析时间戳失败: {timestamp}")
            return 0.0
            
    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频文件时长
        Args:
            audio_path: 音频文件路径
        Returns:
            float: 音频时长（秒）
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ]
            duration = float(subprocess.check_output(cmd).decode().strip())
            print(f"🎵 音频时长: {duration:.3f}秒")
            return duration
        except Exception as e:
            print(f"❌ 获取音频时长失败: {str(e)}")
            return 0.0
        
    def _clip_video(self, start_time: float, end_time: float, audio_path: str, output_path: str) -> bool:
        """剪辑视频片段
        Args:
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            audio_path: 音频文件路径
            output_path: 输出文件路径
        Returns:
            bool: 是否成功
        """
        try:
            # 1. 获取音频时长
            audio_duration = self._get_audio_duration(audio_path)
            if audio_duration == 0:
                print(f"❌ 音频时长为0，跳过处理")
                return False
                
            # 2. 计算视频片段时长
            video_duration = end_time - start_time
            print(f"📊 视频片段信息:")
            print(f"   - 开始时间: {start_time:.3f}秒")
            print(f"   - 结束时间: {end_time:.3f}秒") 
            print(f"   - 视频时长: {video_duration:.3f}秒")
            print(f"   - 音频时长: {audio_duration:.3f}秒")
            
            # 3. 计算需要定格的时长
            freeze_duration = max(0, audio_duration - video_duration)
            print(f"⏱️ 定格信息:")
            print(f"   - 需要定格: {freeze_duration:.3f}秒")
            
            # 4. 剪辑视频到临时文件（使用详细的编码参数）
            temp_video = output_path + ".temp.mp4"
            cmd = [
                'ffmpeg', '-y',
                '-i', self.video_path,
                '-ss', f"{start_time:.3f}",
                '-t', f"{video_duration:.3f}",
                '-vf', f"tpad=stop_mode=clone:stop_duration={freeze_duration}",
                # 视频编码参数
                '-c:v', 'libx264',
                '-profile:v', 'high',
                '-preset', 'fast',
                '-crf', '23',
                '-r', '30',  # 30fps
                '-b:v', '2500k',  # 2500kb/s比特率
                '-maxrate', '3000k',
                '-bufsize', '6000k',
                '-pix_fmt', 'yuv420p',
                # 移除音频
                '-an',
                temp_video
            ]
            
            print(f"🎬 剪辑视频命令:")
            print(f"   {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ 剪辑视频失败:")
                print(f"   错误输出: {result.stderr}")
                return False
            
            # 5. 合并视频和音频（使用详细的音频编码参数）
            cmd = [
                'ffmpeg', '-y',
                '-i', temp_video,
                '-i', audio_path,
                # 复制视频流
                '-c:v', 'copy',
                # 音频编码参数
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '44100',
                '-ac', '2',  # 立体声
                output_path
            ]
            
            print(f"🔊 合并音频命令:")
            print(f"   {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ 合并音频失败:")
                print(f"   错误输出: {result.stderr}")
                return False
            
            # 6. 清理临时文件
            if os.path.exists(temp_video):
                os.remove(temp_video)
                print(f"🧹 清理临时文件: {temp_video}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 处理视频片段失败: {str(e)}")
            print(f"错误输出: {e.stderr.decode('utf-8', errors='ignore')}")
            return False
        except Exception as e:
            print(f"❌ 处理视频片段失败: {str(e)}")
            return False
            
    def _merge_audio_files(self, audio_paths: Dict[str, str], output_audio: str) -> bool:
        """合并多个音频文件，按固定顺序：en -> zh -> notes"""
        try:
            self.logger.info(f"开始合并音频文件:")
            self.logger.info(f"- 音频文件: {audio_paths}")
            self.logger.info(f"- 输出路径: {output_audio}")
            
            # 按固定顺序准备音频文件
            audio_sequence = ['en', 'zh', 'notes']
            audio_files = []
            
            # 验证所有必需的音频文件
            for audio_type in audio_sequence:
                if audio_type not in audio_paths:
                    self.logger.error(f"缺少{audio_type}音频文件")
                    return False
                    
                audio_file = audio_paths[audio_type]
                if not os.path.exists(audio_file):
                    self.logger.error(f"音频文件不存在: {audio_file}")
                    return False
                    
                # 检查音频文件大小
                file_size = os.path.getsize(audio_file)
                if file_size == 0:
                    self.logger.error(f"音频文件为空: {audio_file}")
                    return False
                self.logger.info(f"- {audio_type}音频文件大小: {file_size} 字节")
                
                audio_files.append(audio_file)
            
            # 构建ffmpeg命令
            filter_complex = []
            inputs = []
            for i, audio_file in enumerate(audio_files):
                inputs.extend(['-i', audio_file])
                filter_complex.append(f'[{i}:a]')
            
            # 使用concat过滤器合并音频
            filter_str = f"{''.join(filter_complex)}concat=n={len(audio_files)}:v=0:a=1[outa]"
            
            cmd = [
                'ffmpeg', '-y'
            ] + inputs + [
                '-filter_complex', filter_str,
                '-map', '[outa]',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '44100',
                '-ac', '2',
                output_audio
            ]
            
            self.logger.info(f"合并音频命令:")
            self.logger.info(f"命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"合并音频失败:")
                self.logger.error(f"错误输出: {result.stderr}")
                return False
                
            # 检查合并后的音频文件大小
            if not os.path.exists(output_audio):
                self.logger.error(f"合并后的音频文件不存在: {output_audio}")
                return False
                
            merged_size = os.path.getsize(output_audio)
            if merged_size == 0:
                self.logger.error(f"合并后的音频文件为空")
                return False
            self.logger.info(f"合并后的音频文件大小: {merged_size} 字节")
            
            self.logger.info(f"音频合并成功: {output_audio}")
            return True
            
        except Exception as e:
            self.logger.error(f"合并音频失败: {str(e)}", exc_info=True)
            return False

    def _create_blurred_freeze_video(self, video_path: str, duration: float, blur_strength: int = 20) -> str:
        """创建模糊定格视频"""
        try:
            self.logger.info(f"开始创建模糊定格视频:")
            self.logger.info(f"- 输入视频: {video_path}")
            self.logger.info(f"- 定格时长: {duration:.3f}秒")
            self.logger.info(f"- 模糊强度: {blur_strength}")
            
            # 临时文件路径
            temp_dir = os.path.dirname(video_path)
            temp_frame = os.path.join(temp_dir, "temp_last_frame.png")
            temp_blur_video = os.path.join(temp_dir, "temp_blur.mp4")
            
            # 1. 提取最后一帧并应用模糊效果
            cmd = [
                'ffmpeg', '-y',
                '-sseof', '-1',  # 从视频末尾开始
                '-i', video_path,
                '-update', '1',   # 只更新一帧
                '-vf', f"boxblur={blur_strength}:2:{blur_strength}:2:0",
                '-frames:v', '1',
                temp_frame
            ]
            
            self.logger.info(f"提取并模糊最后一帧:")
            self.logger.info(f"命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"提取帧失败:")
                self.logger.error(f"错误输出: {result.stderr}")
                return None
            
            if not os.path.exists(temp_frame):
                self.logger.error(f"提取的帧文件不存在: {temp_frame}")
                return None
            
            self.logger.info(f"成功提取并模糊最后一帧: {temp_frame}")
            
            # 2. 将模糊帧转换为视频
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', temp_frame,
                '-t', f"{duration}",
                '-c:v', 'libx264',
                '-tune', 'stillimage',
                '-pix_fmt', 'yuv420p',
                '-b:v', '2500k',  # 添加视频比特率
                temp_blur_video
            ]
            
            self.logger.info(f"生成模糊定格视频:")
            self.logger.info(f"命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 清理临时帧文件
            if os.path.exists(temp_frame):
                os.remove(temp_frame)
                self.logger.info(f"清理临时帧文件: {temp_frame}")
            
            if result.returncode != 0:
                self.logger.error(f"生成模糊视频失败:")
                self.logger.error(f"错误输出: {result.stderr}")
                return None
            
            if not os.path.exists(temp_blur_video):
                self.logger.error(f"生成的模糊视频文件不存在: {temp_blur_video}")
                return None
                
            # 验证生成的视频文件大小
            video_size = os.path.getsize(temp_blur_video)
            if video_size == 0:
                self.logger.error(f"生成的模糊视频文件为空")
                return None
            self.logger.info(f"模糊视频文件大小: {video_size} 字节")
            
            self.logger.info(f"成功生成模糊定格视频: {temp_blur_video}")
            return temp_blur_video
            
        except Exception as e:
            self.logger.error(f"创建模糊定格视频失败: {str(e)}", exc_info=True)
            return None

    def _create_complete_version(self, start_time: float, end_time: float, 
                               audio_paths: Dict[str, str], output_path: str) -> bool:
        """创建完整版视频（包含所有音频）"""
        try:
            self.logger.info(f"\n开始创建完整版视频:")
            self.logger.info(f"- 开始时间: {start_time:.3f}秒")
            self.logger.info(f"- 结束时间: {end_time:.3f}秒")
            self.logger.info(f"- 音频文件: {audio_paths}")
            self.logger.info(f"- 输出路径: {output_path}")
            
            # 1. 合并音频文件
            temp_audio = output_path + ".temp.aac"
            if not self._merge_audio_files(audio_paths, temp_audio):
                self.logger.error("合并音频文件失败")
                return False
            
            # 2. 获取合并后音频的总时长
            total_audio_duration = self._get_audio_duration(temp_audio)
            if total_audio_duration == 0:
                self.logger.error("获取音频时长失败或音频时长为0")
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)
                return False
            
            # 3. 计算视频片段时长
            video_duration = end_time - start_time
            self.logger.info(f"视频信息:")
            self.logger.info(f"- 视频时长: {video_duration:.3f}秒")
            self.logger.info(f"- 音频总时长: {total_audio_duration:.3f}秒")
            
            # 4. 计算需要定格的时长
            freeze_duration = max(0, total_audio_duration - video_duration)
            self.logger.info(f"定格信息:")
            self.logger.info(f"- 需要定格: {freeze_duration:.3f}秒")
            
            # 5. 剪辑原始视频片段
            temp_video = output_path + ".temp.mp4"
            cmd = [
                'ffmpeg', '-y',
                '-i', self.video_path,
                '-ss', f"{start_time:.3f}",
                '-t', f"{video_duration:.3f}",
                '-c:v', 'libx264',
                '-profile:v', 'high',
                '-preset', 'fast',
                '-crf', '23',
                '-r', '30',
                '-pix_fmt', 'yuv420p',
                '-an',
                temp_video
            ]
            
            self.logger.info(f"剪辑视频命令:")
            self.logger.info(f"命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"剪辑视频失败:")
                self.logger.error(f"错误输出: {result.stderr}")
                return False
            
            # 6. 如果需要定格，创建模糊定格视频
            if freeze_duration > 0:
                self.logger.info(f"开始创建模糊定格部分...")
                blur_video = self._create_blurred_freeze_video(temp_video, freeze_duration)
                if not blur_video:
                    self.logger.error("创建模糊定格视频失败")
                    return False
                
                # 7. 拼接原视频和模糊定格视频
                temp_concat = output_path + ".concat.txt"
                with open(temp_concat, 'w', encoding='utf-8') as f:
                    # 使用绝对路径
                    temp_video_abs = os.path.abspath(temp_video)
                    blur_video_abs = os.path.abspath(blur_video)
                    f.write(f"file '{temp_video_abs}'\n")
                    f.write(f"file '{blur_video_abs}'\n")
                
                final_video = output_path + ".final.mp4"
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', temp_concat,
                    '-c', 'copy',
                    final_video
                ]
                
                self.logger.info(f"拼接视频命令:")
                self.logger.info(f"命令: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # 更新临时视频路径
                if os.path.exists(temp_video):
                    os.remove(temp_video)
                    self.logger.info(f"清理原始临时视频: {temp_video}")
                temp_video = final_video
                
                # 清理临时文件
                for temp_file in [blur_video, temp_concat]:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        self.logger.info(f"清理临时文件: {temp_file}")
                
                if result.returncode != 0:
                    self.logger.error(f"拼接视频失败:")
                    self.logger.error(f"错误输出: {result.stderr}")
                    return False
            else:
                self.logger.info("无需创建定格部分，音频时长小于等于视频时长")
            
            # 8. 合并视频和音频
            cmd = [
                'ffmpeg', '-y',
                '-i', temp_video,
                '-i', temp_audio,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '44100',
                '-ac', '2',
                output_path
            ]
            
            self.logger.info(f"合并音频命令:")
            self.logger.info(f"命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 9. 清理所有临时文件
            for temp_file in [temp_video, temp_audio]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    self.logger.info(f"清理临时文件: {temp_file}")
            
            if result.returncode != 0:
                self.logger.error(f"合并音频失败:")
                self.logger.error(f"错误输出: {result.stderr}")
                return False
            
            self.logger.info(f"成功生成完整版视频: {os.path.basename(output_path)}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建完整版视频失败: {str(e)}", exc_info=True)
            # 确保清理所有临时文件
            for temp_file in [
                output_path + ".temp.aac",
                output_path + ".temp.mp4",
                output_path + ".final.mp4",
                output_path + ".concat.txt"
            ]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            return False

    def process_clips(self) -> List[str]:
        """处理所有视频片段
        Returns:
            List[str]: 生成的视频片段路径列表
        """
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 加载分析结果
        data = self._load_analysis()
        if not data:
            return []
            
        result_clips = []
        
        # 处理词汇
        if 'vocabulary' in data:
            for item in data['vocabulary']:
                if 'start_time' not in item or 'end_time' not in item or 'text' not in item:
                    continue
                    
                start_time = self._parse_timestamp(item['start_time'])
                end_time = self._parse_timestamp(item['end_time'])
                item_id = item['text']
                
                # 获取音频文件路径
                audio_paths = self._get_audio_paths('vocabulary', item_id)
                if not audio_paths:
                    print(f"⚠️ 未找到任何音频文件: {item_id}")
                    continue
                
                # 设置输出路径
                clean_id = self._clean_filename(item_id)
                
                # 创建对应的输出子目录（移到外面）
                output_subdir = os.path.join(self.output_dir, "vocabulary", clean_id)
                os.makedirs(output_subdir, exist_ok=True)
                
                # 处理每种音频类型
                for audio_type, audio_path in audio_paths.items():
                    # 检查是否需要生成该类型的视频
                    if audio_type not in self.generate_types:
                        continue
                        
                    output_path = os.path.join(output_subdir, f"{clean_id}_{audio_type}.mp4")
                    
                    # 剪辑视频
                    print(f"\n🎬 处理词汇片段: {item_id} ({audio_type})")
                    print(f"⏱️ 时间范围: {start_time:.2f}s - {end_time:.2f}s")
                    
                    if self._clip_video(start_time, end_time, audio_path, output_path):
                        result_clips.append(output_path)
                        print(f"✅ 生成视频片段: {os.path.basename(output_path)}")
                        
                # 创建完整版视频（如果需要）
                if VideoTypes.COMPLETE in self.generate_types:
                    complete_output_path = os.path.join(output_subdir, f"{clean_id}_complete.mp4")
                    print(f"\n🎬 处理完整版视频: {item_id}")
                    print(f"⏱️ 时间范围: {start_time:.2f}s - {end_time:.2f}s")
                    
                    if self._create_complete_version(start_time, end_time, audio_paths, complete_output_path):
                        result_clips.append(complete_output_path)
                        print(f"✅ 生成完整版视频: {os.path.basename(complete_output_path)}")
        
        # 处理短语
        if 'phrases' in data:
            for item in data['phrases']:
                if 'start_time' not in item or 'end_time' not in item or 'text' not in item:
                    continue
                    
                start_time = self._parse_timestamp(item['start_time'])
                end_time = self._parse_timestamp(item['end_time'])
                item_id = item['text']
                
                # 获取音频文件路径
                audio_paths = self._get_audio_paths('phrases', item_id)
                if not audio_paths:
                    print(f"⚠️ 未找到任何音频文件: {item_id}")
                    continue
                
                # 设置输出路径
                clean_id = self._clean_filename(item_id)
                
                # 创建对应的输出子目录（移到外面）
                output_subdir = os.path.join(self.output_dir, "phrases", clean_id)
                os.makedirs(output_subdir, exist_ok=True)
                
                # 处理每种音频类型
                for audio_type, audio_path in audio_paths.items():
                    # 检查是否需要生成该类型的视频
                    if audio_type not in self.generate_types:
                        continue
                        
                    output_path = os.path.join(output_subdir, f"{clean_id}_{audio_type}.mp4")
                    
                    # 剪辑视频
                    print(f"\n🎬 处理短语片段: {item_id} ({audio_type})")
                    print(f"⏱️ 时间范围: {start_time:.2f}s - {end_time:.2f}s")
                    
                    if self._clip_video(start_time, end_time, audio_path, output_path):
                        result_clips.append(output_path)
                        print(f"✅ 生成视频片段: {os.path.basename(output_path)}")
                        
                # 创建完整版视频（如果需要）
                if VideoTypes.COMPLETE in self.generate_types:
                    complete_output_path = os.path.join(output_subdir, f"{clean_id}_complete.mp4")
                    print(f"\n🎬 处理完整版视频: {item_id}")
                    print(f"⏱️ 时间范围: {start_time:.2f}s - {end_time:.2f}s")
                    
                    if self._create_complete_version(start_time, end_time, audio_paths, complete_output_path):
                        result_clips.append(complete_output_path)
                        print(f"✅ 生成完整版视频: {os.path.basename(complete_output_path)}")
        
        # 处理表达
        if 'expressions' in data:
            for item in data['expressions']:
                if 'start_time' not in item or 'end_time' not in item or 'text' not in item:
                    continue
                    
                start_time = self._parse_timestamp(item['start_time'])
                end_time = self._parse_timestamp(item['end_time'])
                item_id = item['text']
                
                # 获取音频文件路径
                audio_paths = self._get_audio_paths('expressions', item_id)
                if not audio_paths:
                    print(f"⚠️ 未找到任何音频文件: {item_id}")
                    continue
                
                # 设置输出路径
                clean_id = self._clean_filename(item_id)
                
                # 创建对应的输出子目录（移到外面）
                output_subdir = os.path.join(self.output_dir, "expressions", clean_id)
                os.makedirs(output_subdir, exist_ok=True)
                
                # 处理每种音频类型
                for audio_type, audio_path in audio_paths.items():
                    # 检查是否需要生成该类型的视频
                    if audio_type not in self.generate_types:
                        continue
                        
                    output_path = os.path.join(output_subdir, f"{clean_id}_{audio_type}.mp4")
                    
                    # 剪辑视频
                    print(f"\n🎬 处理表达片段: {item_id} ({audio_type})")
                    print(f"⏱️ 时间范围: {start_time:.2f}s - {end_time:.2f}s")
                    
                    if self._clip_video(start_time, end_time, audio_path, output_path):
                        result_clips.append(output_path)
                        print(f"✅ 生成视频片段: {os.path.basename(output_path)}")
                        
                # 创建完整版视频（如果需要）
                if VideoTypes.COMPLETE in self.generate_types:
                    complete_output_path = os.path.join(output_subdir, f"{clean_id}_complete.mp4")
                    print(f"\n🎬 处理完整版视频: {item_id}")
                    print(f"⏱️ 时间范围: {start_time:.2f}s - {end_time:.2f}s")
                    
                    if self._create_complete_version(start_time, end_time, audio_paths, complete_output_path):
                        result_clips.append(complete_output_path)
                        print(f"✅ 生成完整版视频: {os.path.basename(complete_output_path)}")
        
        return result_clips 
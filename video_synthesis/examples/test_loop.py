"""
测试视频循环逻辑
1. 生成测试视频
2. 测试循环和抠像效果
"""

import os
import sys
import math
import logging
from datetime import datetime
import subprocess

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(current_dir)

from video_synthesis.utils.ffmpeg_utils import get_video_duration, run_ffmpeg_command

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/test_loop_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('test_loop')

def run_ffmpeg_command(cmd):
    """运行ffmpeg命令"""
    print("\n处理中...")
    print(f"执行命令: {' '.join(cmd)}")
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    
    if stdout:
        print(stdout.decode('utf-8', errors='ignore'))
    if stderr:
        print(stderr.decode('utf-8', errors='ignore'))
    
    success = process.returncode == 0
    print("处理中完成")
    return success

def create_test_videos():
    """创建测试视频"""
    logger.info("开始创建测试视频")
    
    # 创建输出目录
    os.makedirs("temp", exist_ok=True)
    
    # 1. 创建10秒红色背景视频（主视频）
    main_video = "temp/main_red.mp4"
    main_cmd = [
        "ffmpeg",
        "-f", "lavfi",
        "-i", "color=c=red:s=720x1280:r=25",
        "-t", "10",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-y",
        main_video
    ]
    logger.info("创建主视频...")
    success = run_ffmpeg_command(main_cmd)
    if not os.path.exists(main_video) or os.path.getsize(main_video) == 0:
        logger.error("主视频文件创建失败或为空")
        return None, None
    logger.info("主视频创建成功")
    
    # 2. 使用实际的绿幕视频
    green_screen_dir = "assets/pip3_videos"
    if not os.path.exists(green_screen_dir):
        logger.error(f"绿幕视频目录不存在: {green_screen_dir}")
        return None, None
        
    videos = [f for f in os.listdir(green_screen_dir) if f.endswith(('.mp4', '.mov'))]
    if not videos:
        logger.error("未找到绿幕视频")
        return None, None
        
    green_video = os.path.join(green_screen_dir, videos[0])  # 使用第一个视频
    logger.info(f"使用绿幕视频: {green_video}")
    
    return main_video, green_video

def test_loop_logic(main_video: str, green_video: str):
    """测试循环逻辑"""
    logger.info("开始测试循环逻辑")
    
    # 获取视频时长
    main_duration = get_video_duration(main_video)
    green_duration = get_video_duration(green_video)
    
    if not main_duration or not green_duration:
        logger.error("无法获取视频时长")
        return False
    
    # 计算循环次数
    loop_count = math.ceil(main_duration / green_duration)
    logger.info(f"主视频时长: {main_duration}秒")
    logger.info(f"绿幕视频时长: {green_duration}秒")
    logger.info(f"需要循环次数: {loop_count}")
    
    # 构建新的filter_complex
    filter_complex = [
        # 处理背景视频
        "[0:v]format=yuv420p,fps=30[bg]",
        
        # 处理绿幕视频 - 简化的处理方式
        "[1:v]format=yuv444p,fps=30[fmt]",
        "[fmt]colorkey=0x00FF00:0.3:0.2[keyed]",
        "[keyed]scale=iw*0.3:-1[scaled]",
        
        # 循环处理 - 使用简单的loop
        f"[scaled]loop=loop={loop_count}:size=1:start=0[looped]",
        
        # 时长控制
        f"[looped]trim=0:{main_duration},setpts=PTS-STARTPTS[timed]",
        
        # 叠加到背景视频
        "[bg][timed]overlay=x=W-w-10:y=H-h+10:shortest=1[out]"
    ]
    
    # 构建FFmpeg命令
    output_video = "temp/test_result.mp4"
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", main_video,
        "-i", green_video,
        "-filter_complex", ";".join(filter_complex),
        "-map", "[out]",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-r", "30",
        "-y",
        output_video
    ]
    
    # 打印完整的filter_complex以便调试
    logger.info("Filter Complex:")
    logger.info(";".join(filter_complex))
    
    # 执行命令
    logger.info("开始合成测试视频...")
    success = run_ffmpeg_command(ffmpeg_cmd)
    
    if success and os.path.exists(output_video) and os.path.getsize(output_video) > 0:
        logger.info(f"测试视频已生成: {output_video}")
        print(f"\n✅ 测试视频已生成: {output_video}")
        return True
    else:
        logger.error("测试视频生成失败")
        print("\n❌ 测试视频生成失败")
        return False

def main():
    """主函数"""
    # 1. 创建测试视频
    main_video, green_video = create_test_videos()
    if not main_video or not green_video:
        print("❌ 创建测试视频失败")
        return
    
    # 2. 测试循环逻辑
    test_loop_logic(main_video, green_video)

if __name__ == "__main__":
    main() 
"""
运行脚本
"""

import os
import sys
import io

# 设置标准输出编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 导入主程序和字幕处理器
from video_synthesis.main import main as video_main
from video_synthesis.examples.process_subtitle import process_subtitle

def process_video_subtitle(video_name: str):
    """处理字幕、生成音频并剪辑视频片段"""
    try:
        print(f"\n[INFO] 开始处理视频字幕: {video_name}")
        
        # 使用一体化处理功能（使用默认的影视解说小帅音色）
        result_dir = process_subtitle(video_name=video_name)
        
        if result_dir:
            print("\n[SUCCESS] 字幕处理成功完成！")
            print(f"输出目录: {result_dir}")
            return True
        else:
            print("\n[ERROR] 字幕处理失败，请查看日志文件了解详情。")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] 字幕处理时发生错误: {str(e)}")
        return False

if __name__ == "__main__":
    # 获取命令行参数
    if len(sys.argv) < 2:
        print("使用方法: python run.py <背景类型(1或2)>")
        sys.exit(1)
    
    try:
        # 保存原始的命令行参数
        original_argv = sys.argv[:]
        
        # 1. 从视频处理函数获取视频名称（但不执行处理）
        sys.argv = [sys.argv[0]] + [sys.argv[1]]
        video_name = video_main(get_name_only=True)  # 仅获取视频名称
        
        if not video_name:
            print("\n[WARNING] 未能获取视频名称")
            sys.exit(1)
            
        # 2. 先处理字幕、生成音频并剪辑视频片段
        subtitle_success = process_video_subtitle(video_name)
        if not subtitle_success:
            print("\n[WARNING] 字幕处理失败，是否继续视频合成？(y/n)")
            response = input().lower()
            if response != 'y':
                sys.exit(1)
        
        # 3. 执行视频合成
        print("\n[INFO] 开始视频合成...")
        video_main()  # 执行实际的视频处理
        
        print("\n[SUCCESS] 所有处理完成！")
        
    except Exception as e:
        print(f"[ERROR] 发生错误: {str(e)}")
        sys.exit(1) 
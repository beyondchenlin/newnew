"""
FFmpeg工具函数模块
"""
import subprocess
from queue import Queue, Empty
from threading import Thread

def run_ffmpeg_command(cmd, description="处理中"):
    """运行ffmpeg命令
    Args:
        cmd (list): ffmpeg命令列表
        description (str): 处理描述
    """
    print(f"\n{description}...")
    print("执行命令:", ' '.join(cmd))
    
    # 创建进程
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8',  # 使用UTF-8编码
        errors='replace'   # 处理无法解码的字符
    )
    
    # 创建队列存储输出
    output_queue = Queue()
    error_output = []
    
    # 定义输出处理函数
    def enqueue_output(out, queue):
        try:
            for line in iter(out.readline, ''):
                queue.put(line)
        except Exception as e:
            print(f"读取输出时出错: {str(e)}")
        finally:
            out.close()
    
    # 创建线程处理输出
    stdout_thread = Thread(target=enqueue_output, args=(process.stdout, output_queue))
    stderr_thread = Thread(target=enqueue_output, args=(process.stderr, output_queue))
    stdout_thread.daemon = True
    stderr_thread.daemon = True
    stdout_thread.start()
    stderr_thread.start()
    
    # 实时处理输出
    while True:
        try:
            # 检查进程是否结束
            if process.poll() is not None and output_queue.empty():
                break
            
            try:
                line = output_queue.get_nowait()
            except Empty:
                continue
            
            # 处理输出
            if line.startswith("frame="):
                print(line.strip(), end='\r')
            else:
                print(line.strip())
                error_output.append(line.strip())
                
        except Exception as e:
            print(f"处理输出时出错: {str(e)}")
            break
    
    # 等待进程结束
    process.stdout.close()
    process.stderr.close()
    process.wait()
    
    if process.returncode != 0:
        error_msg = '\n'.join(error_output) if error_output else "未知错误"
        print(f"错误: {description}失败")
        print(f"错误信息: {error_msg}")
        raise Exception(f"{description}失败: {error_msg}")
    
    print(f"{description}完成")

def get_video_duration(video_path):
    """获取视频时长
    Args:
        video_path (str): 视频文件路径
    Returns:
        float: 视频时长（秒）
    """
    cmd = [
        'ffprobe', 
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    duration = float(result.stdout.strip())
    print(f"视频时长: {duration:.2f}秒")
    return duration

def get_video_dimensions(video_path):
    """获取视频尺寸
    Args:
        video_path (str): 视频文件路径
    Returns:
        tuple: (width, height)
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=s=x:p=0',
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    width, height = map(int, result.stdout.strip().split('x'))
    return width, height 
"""
文件操作工具函数模块
"""
import os
import glob
import random
import pandas as pd
import json

def load_history():
    """加载历史记录
    Returns:
        dict: 历史记录数据
    """
    history_file = "logs/video_history.json"
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"folders": [], "videos": [], "texts": [], "side_videos": []}
    return {"folders": [], "videos": [], "texts": [], "side_videos": []}

def save_history(history):
    """保存历史记录
    Args:
        history (dict): 历史记录数据
    """
    history_file = "logs/video_history.json"
    # 只保留最近10次的记录
    for key in history:
        history[key] = history[key][-10:]
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def get_random_video(folder_path, exclude_video=None):
    """从指定文件夹中随机选择一个视频（包括子文件夹）
    Args:
        folder_path (str): 视频文件夹路径
        exclude_video (str): 要排除的视频文件名（避免重复）
    Returns:
        tuple: (视频路径, CSV文件路径)
    """
    history = load_history()
    
    folder_path = os.path.normpath(folder_path)
    if not os.path.exists(folder_path):
        raise Exception(f"文件夹不存在: {folder_path}")
    
    subdirs = [d for d in glob.glob(os.path.join(folder_path, "*")) 
              if os.path.isdir(d)]
    
    if not subdirs:
        raise Exception(f"在 {folder_path} 中没有找到子文件夹")
    
    # 排除最近使用过的文件夹
    available_dirs = [d for d in subdirs if os.path.basename(d) not in history['folders']]
    if not available_dirs:
        print("警告：所有文件夹都已使用过，重置历史记录")
        available_dirs = subdirs
        history['folders'] = []
    
    selected_dir = random.choice(available_dirs)
    print(f"\n选择子文件夹: {os.path.basename(selected_dir)}")
    
    videos = glob.glob(os.path.join(selected_dir, "*.mp4"))
    csv_files = glob.glob(os.path.join(selected_dir, "*.csv"))
    
    if not videos:
        raise Exception(f"在子文件夹 {selected_dir} 中没有找到视频文件")
    
    if not csv_files:
        print(f"警告: 在子文件夹 {selected_dir} 中没有找到CSV文件")
        csv_path = None
    else:
        csv_path = csv_files[0]
        print(f"找到CSV文件: {os.path.basename(csv_path)}")
    
    videos = [os.path.normpath(v) for v in videos]
    
    if exclude_video:
        videos = [v for v in videos if os.path.basename(v) != exclude_video]
    
    # 排除最近使用过的视频
    available_videos = [v for v in videos if os.path.basename(v) not in history['videos']]
    if not available_videos:
        print("警告：当前文件夹中所有视频都已使用过，重置该文件夹的历史记录")
        available_videos = videos
        history['videos'] = []
    
    selected = random.choice(available_videos)
    print(f"选择视频: {os.path.basename(selected)}")
    print(f"完整路径: {selected}")
    
    if not os.path.isfile(selected):
        raise Exception(f"选中的视频文件不存在: {selected}")
    
    # 更新历史记录
    history['folders'].append(os.path.basename(selected_dir))
    history['videos'].append(os.path.basename(selected))
    save_history(history)
    
    return selected, csv_path

def read_text_from_excel(excel_path):
    """从CSV文件中读取文字内容
    Args:
        excel_path (str): CSV文件路径
    Returns:
        tuple: (顶部主标题, 顶部副标题, 底部文字)
    """
    try:
        history = load_history()
        
        if not excel_path:
            print("\n未找到CSV文件，使用默认文字")
            return ("默认主标题", "默认副标题", "默认底部文字")
        
        if not os.path.exists(excel_path):
            raise FileNotFoundError(f"找不到CSV文件: {excel_path}")
        
        print(f"\n正在读取CSV文件: {excel_path}")
        df = pd.read_csv(excel_path)
        
        # 验证列名是否正确
        required_columns = ['主标题', '副标题', '底部文字']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"CSV文件缺少必需的列: {missing_columns}")
        
        # 生成所有可能的文字组合
        text_combinations = []
        for i in range(len(df)):
            combo = (
                str(df.iloc[i]['主标题']).strip(),
                str(df.iloc[i]['副标题']).strip(),
                str(df.iloc[i]['底部文字']).strip()
            )
            text_key = '|'.join(combo)
            if text_key not in history['texts']:
                text_combinations.append(combo)
        
        if not text_combinations:
            print("警告：所有文字组合都已使用过，重置历史记录")
            text_combinations = [(
                str(df.iloc[i]['主标题']).strip(),
                str(df.iloc[i]['副标题']).strip(),
                str(df.iloc[i]['底部文字']).strip()
            ) for i in range(len(df))]
            history['texts'] = []
        
        # 随机选择一个未使用过的组合
        selected_combo = random.choice(text_combinations)
        title1, title2, bottom_text = selected_combo
        
        # 检查是否有空值，使用默认值替代
        if not title1:
            title1 = "默认主标题"
        if not title2:
            title2 = "默认副标题"
        if not bottom_text:
            bottom_text = "默认底部文字"
        
        print("\n从CSV中读取的文字内容：")
        print(f"顶部主标题：{title1}")
        print(f"顶部副标题：{title2}")
        print(f"底部文字：{bottom_text}")
        
        # 更新历史记录
        history['texts'].append('|'.join(selected_combo))
        save_history(history)
        
        return (title1, title2, bottom_text)
    except Exception as e:
        print(f"读取CSV文件失败: {str(e)}")
        print("将使用默认文字")
        return ("默认主标题", "默认副标题", "默认底部文字")

def ensure_directory(directory):
    """确保目录存在，如果不存在则创建
    Args:
        directory (str): 目录路径
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"创建目录: {directory}")

def cleanup_temp_files(temp_dir):
    """清理临时文件和目录
    Args:
        temp_dir (str): 临时目录路径
    """
    if os.path.exists(temp_dir):
        for file in glob.glob(os.path.join(temp_dir, "*")):
            os.remove(file)
            print(f"删除: {file}")
        os.rmdir(temp_dir)
        print(f"删除: {temp_dir} 文件夹") 
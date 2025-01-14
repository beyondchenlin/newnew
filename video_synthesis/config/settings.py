"""
全局配置文件
"""

# 视频处理相关配置
VIDEO_SETTINGS = {
    'MAIN_VIDEO_SCALE': 0.6,     # 左侧主视频尺寸（占原视频的60%）
    'MAIN_VIDEO_X': 0,           # 左侧主视频的x坐标（紧贴左边）
    'CROP_MARGIN': 50,           # 上下裁切像素数
    'BLUR_SIGMA': 30,            # 高斯模糊程度
    'SIDE_VIDEO_SCALE': 0.3,     # 右侧视频尺寸（占原视频的30%）
    'SIDE_VIDEO_X': 470,         # 右侧视频的x坐标
}

# 文字效果相关配置
TEXT_SETTINGS = {
    'TOP_MARGIN_X': 150,         # 顶部文字左右边距
    'BOTTOM_MARGIN_X': 70,       # 底部文字左右边距
    'BOTTOM_BOX_MARGIN': 70,     # 底部黄色背景框左右边距
    'TITLE1_Y': 100,            # 主标题垂直位置
    'TITLE2_Y': 200,            # 副标题垂直位置
    'TITLE_FONT_SIZE': 120,     # 顶部文字基准大小
    'BOTTOM_FONT_SIZE': 100,    # 底部文字基准大小
}

# 字体配置
FONT_OPTIONS = [
    ("fonts/方正粗黑宋简体.ttf", "方正粗黑宋简体"),
    ("C:\\Windows\\Fonts\\msyhbd.ttc", "微软雅黑粗体"),
    ("C:\\Windows\\Fonts\\simhei.ttf", "黑体"),
]

# 路径配置
PATH_SETTINGS = {
    'PIP1_FOLDER': "assets/pip1_videos",  # 主视频目录
    'PIP2_FOLDER': "assets/pip2_videos",  # 侧视频目录
    'OUTPUTS_FOLDER': "outputs",          # 输出目录
    'TEMP_DIR': "temp"                    # 临时文件夹
}

# 字幕背景设置
SUBTITLE_BACKGROUND = {
    'WIDTH': 600,                # 黄色背景的宽度（像素）
    'HEIGHT': 150,               # 黄色背景的高度（像素）
    'COLOR': (0, 255, 255),      # 背景颜色，BGR格式：(Blue=0, Green=255, Red=255) 表示黄色
    'POSITION_X': 'center',      # 水平位置：'center'表示居中，或具体的像素值
    'POSITION_Y': 120,           # 垂直位置：距离顶部的像素值
    'SHOW_TIME': 6               # 开始显示的时间（秒）
} 
"""
字幕分析示例脚本
"""

import os
import sys
import traceback
import logging
from datetime import datetime
from video_synthesis.core.deepseek import SubtitleAnalyzer, save_analysis_results

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/subtitle_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

def main():
    try:
        # 检查文件路径
        subtitle_file = "assets/pip1_videos/tt/tt_en.srt"
        if not os.path.exists(subtitle_file):
            logging.error(f"字幕文件不存在: {subtitle_file}")
            return

        logging.info(f"字幕文件存在: {subtitle_file}")
        
        # 初始化分析器
        analyzer = SubtitleAnalyzer()
        logging.info("分析器初始化成功")
        
        # 创建输出目录
        output_dir = "subtitles"
        os.makedirs(output_dir, exist_ok=True)
        logging.info(f"输出目录创建成功: {output_dir}")
        
        # 设置输出文件路径
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(output_dir, f"subtitle_analysis_{timestamp}.json")
        verified_output_file = os.path.join(output_dir, f"subtitle_analysis_verified_{timestamp}.json")
        
        # 处理字幕文件
        logging.info(f"开始分析字幕文件: {subtitle_file}")
        results = analyzer.process_subtitle_file(subtitle_file)
        
        if results:
            # 保存原始分析结果
            save_analysis_results(results, output_file)
            logging.info(f"原始分析结果已保存到: {output_file}")
            
            # 验证时间戳
            logging.info("开始验证时间戳...")
            verified_results = analyzer.verify_timestamp(subtitle_file, results)
            save_analysis_results(verified_results, verified_output_file)
            logging.info(f"验证结果已保存到: {verified_output_file}")
            
            # 打印验证结果摘要
            print("\n验证结果摘要:")
            
            # 验证词汇
            vocab_verified = sum(1 for item in verified_results["vocabulary"] if item.get("verified", False))
            print(f"词汇验证: {vocab_verified}/{len(verified_results['vocabulary'])} 个通过验证")
            
            # 验证短语
            phrases_verified = sum(1 for item in verified_results["phrases"] if item.get("verified", False))
            print(f"短语验证: {phrases_verified}/{len(verified_results['phrases'])} 个通过验证")
            
            # 验证表达
            expressions_verified = sum(1 for item in verified_results["expressions"] if item.get("verified", False))
            print(f"表达验证: {expressions_verified}/{len(verified_results['expressions'])} 个通过验证")
            
            # 打印未通过验证的项目
            print("\n未通过验证的项目:")
            for category in ["vocabulary", "phrases", "expressions"]:
                failed_items = [item for item in verified_results[category] if not item.get("verified", False)]
                if failed_items:
                    print(f"\n{category}:")
                    for item in failed_items:
                        print(f"- {item['text']}: {item.get('error', '未知错误')}")
                        print(f"  时间戳: {item['start_time']} --> {item['end_time']}")
                        print(f"  上下文: {item.get('full_context', '无')}")
                        
        else:
            logging.error("分析过程中出现错误")
            
    except Exception as e:
        logging.error(f"处理过程中出现错误: {str(e)}")
        logging.error(traceback.format_exc())

if __name__ == "__main__":
    main() 
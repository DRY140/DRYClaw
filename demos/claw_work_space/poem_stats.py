#!/usr/bin/env python3
"""
杜甫诗选字数统计脚本
统计每首诗的字数（不包括标点符号）
"""

import re
from pathlib import Path

def count_poem_characters(text: str) -> dict:
    """
    统计每首诗的字数
    
    Args:
        text: 诗歌文本内容
        
    Returns:
        dict: 诗歌名称到字数的映射
    """
    poems = {}
    current_poem = None
    current_lines = []
    
    # 按行处理文本
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # 检测诗歌标题（以##开头）
        if line.startswith('## '):
            # 如果已有诗歌，保存前一首
            if current_poem and current_lines:
                poems[current_poem] = count_characters_in_poem(current_lines)
            
            # 开始新诗歌
            current_poem = line[3:]  # 去掉## 
            current_lines = []
        elif current_poem and line and not line.startswith('#'):
            # 添加诗歌内容行
            current_lines.append(line)
    
    # 添加最后一首诗
    if current_poem and current_lines:
        poems[current_poem] = count_characters_in_poem(current_lines)
    
    return poems

def count_characters_in_poem(lines: list) -> int:
    """
    统计一首诗的字数（不包括标点符号）
    
    Args:
        lines: 诗歌的行列表
        
    Returns:
        int: 字数
    """
    text = ''.join(lines)
    # 移除标点符号（保留汉字）
    cleaned_text = re.sub(r'[，。！？；：、（）「」""\'\'《》]', '', text)
    # 只保留汉字
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', cleaned_text)
    return len(chinese_chars)

def main():
    """主函数"""
    # 读取文件
    file_path = Path('demos/claw_work_space/杜甫诗选.txt')
    if not file_path.exists():
        print(f"错误：文件 {file_path} 不存在")
        return
    
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"读取文件时出错：{e}")
        return
    
    # 统计字数
    poem_stats = count_poem_characters(content)
    
    # 打印结果
    print("杜甫诗选字数统计：")
    print("-" * 30)
    for poem_name, char_count in poem_stats.items():
        print(f"{poem_name}: {char_count} 字")
    
    # 保存结果到文件
    output_path = Path('demos/claw_work_space/poem_stats.txt')
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("杜甫诗选字数统计：\n")
            f.write("=" * 30 + "\n")
            for poem_name, char_count in poem_stats.items():
                f.write(f"{poem_name}: {char_count} 字\n")
        print(f"\n结果已保存到: {output_path}")
    except Exception as e:
        print(f"保存结果时出错：{e}")

if __name__ == "__main__":
    main()
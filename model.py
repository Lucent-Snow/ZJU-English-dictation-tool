import csv
import os
import re
from dataclasses import dataclass
from typing import List

def _sanitize_string(text: str) -> str:
    """清理字符串，移除标准空白符和常见的不可见字符。"""
    if not text:
        return ""
    # 移除零宽空格 (Zero-width space)
    text = text.replace('\u200b', '')
    # 将非中断空格 (Non-breaking space) 替换为标准空格
    text = text.replace('\xa0', ' ')
    # 最后，移除首尾的标准空白符
    return text.strip()

@dataclass(frozen=True)
class WordEntry:
    """
    一个不可变的数据类，用于存放单个单词的所有信息。
    'frozen=True' 确保这个对象在创建后不会被意外修改。
    """
    english: str
    chinese: str
    examples: str

class DataLoader:
    """
    负责从文件中读取和解析单词数据。
    """
    def __init__(self, data_directory: str = "./data"):
        """
        初始化加载器，指定数据存放的根目录。
        """
        self.data_directory = data_directory

    def get_available_books(self) -> List[str]:
        """
        扫描数据目录，返回所有可用的“书本”（即子文件夹）。
        """
        if not os.path.exists(self.data_directory):
            return []
        try:
            return [d for d in os.listdir(self.data_directory) 
                    if os.path.isdir(os.path.join(self.data_directory, d))]
        except Exception as e:
            print(f"Error scanning books: {e}")
            return []

    def get_units_for_book(self, book_name: str) -> List[str]:
        """
        获取指定书本下的所有单元（.csv 文件）。
        """
        book_path = os.path.join(self.data_directory, book_name)
        if not os.path.exists(book_path):
            return []
        try:
            return [f for f in os.listdir(book_path) 
                    if f.endswith('.csv') and os.path.isfile(os.path.join(book_path, f))]
        except Exception as e:
            print(f"Error scanning units for {book_name}: {e}")
            return []

    def load_word_list(self, book_name: str, unit_files: List[str]) -> List[WordEntry]:
        """
        从指定书本的一个或多个单元文件中加载所有单词。
        """
        all_entries: List[WordEntry] = []
        
        for unit_file in unit_files:
            file_path = os.path.join(self.data_directory, book_name, unit_file)
            
            if not os.path.exists(file_path):
                print(f"Warning: File not found {file_path}, skipping.")
                continue

            try:
                with open(file_path, mode='r', encoding='utf-8-sig') as f:
                    # 使用 DictReader 自动读取表头 (english, chinese, examples)
                    reader = csv.DictReader(f)

                    for row in reader:
                        entry = WordEntry(
                            english=_sanitize_string(row.get('english', '')),
                            chinese=_sanitize_string(row.get('chinese', '')),
                            examples=_sanitize_string(row.get('examples', '')) or ""
                        )

                        # 确保我们只添加有英文单词的行
                        if entry.english:
                            all_entries.append(entry)
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

        return all_entries
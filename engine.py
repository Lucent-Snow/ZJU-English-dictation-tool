import json
import os
import random
from dataclasses import asdict
from typing import List, Optional, Set

# 从我们的 model.py 文件中导入数据类
from model import DataLoader, WordEntry

# 定义错题本在硬盘上的存储位置
WRONG_WORDS_FILE = "wrong_words.json"

class GameEngine:
    """
    游戏的核心逻辑和状态管理器。
    这是 "大脑"，它不处理任何UI事务。
    """
    def __init__(self, loader: DataLoader):
        """
        初始化游戏引擎。
        
        Args:
            loader (DataLoader): 一个 DataLoader 实例，用于从文件加载数据。
        """
        self.loader = loader
        
        # 游戏状态
        self.all_words: List[WordEntry] = []      # 当前加载的所有单词
        self.current_deck: List[WordEntry] = []   # 当前正在学习的牌组
        self.current_index: int = 0               # 当前牌组的索引

        self.question_mode: str = "word"
        self.show_first_letter: bool = False
        self.retry_on_wrong: bool = False

        # 错题本状态
        self.wrong_words: Set[WordEntry] = set()

        # 在启动时，从硬盘加载上次的错题
        self._load_wrong_words_from_disk()

    def _load_wrong_words_from_disk(self):
        """
        (私有) 从 .json 文件加载错题本到 self.wrong_words。
        """
        if not os.path.exists(WRONG_WORDS_FILE):
            print("No wrong words file found. Starting fresh.")
            return

        try:
            with open(WRONG_WORDS_FILE, 'r', encoding='utf-8') as f:
                # 从 json 加载字典列表
                data = json.load(f)
                
                # 将字典列表转换回 WordEntry 对象集合
                self.wrong_words = {
                    WordEntry(
                        english=row.get('english', ''),
                        chinese=row.get('chinese', ''),
                        examples=row.get('examples', '')
                    ) for row in data
                }
            print(f"Loaded {len(self.wrong_words)} wrong words from disk.")
        except Exception as e:
            print(f"Error loading wrong words: {e}")

    def _save_wrong_words_to_disk(self):
        """
        (私有) 将当前的 self.wrong_words 集合保存到 .json 文件。
        """
        try:
            with open(WRONG_WORDS_FILE, 'w', encoding='utf-8') as f:
                # dataclasses.asdict 将 WordEntry 实例转换为字典
                # 我们将 Set 转换为 List 以便进行 json 序列化
                data_to_save = [asdict(word) for word in self.wrong_words]
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving wrong words: {e}")

    def start_game(self,
                   book: str,
                   units: List[str],
                   filter_mode: str,
                   order_mode: str,
                   question_mode: str,
                   show_first_letter: bool,
                   retry_on_wrong: bool):
        """
        加载单词并开始一个新游戏 (V2 - 解耦设置)。

        Args:
            book (str): 书本
            units (List[str]): 单元列表
            filter_mode (str): 'all', 'words_only', 'phrases_only'
            order_mode (str): 'sequential', 'random'
            question_mode (str): 'word', 'example'
            show_first_letter (bool): True/False
            retry_on_wrong (bool): True/False
        """
        self.all_words = self.loader.load_word_list(book, units)

        # 应用内容过滤器
        if filter_mode == "words_only":
            temp_deck = [w for w in self.all_words if ' ' not in w.english]
        elif filter_mode == "phrases_only":
            temp_deck = [w for w in self.all_words if ' ' in w.english]
        else:
            temp_deck = self.all_words.copy()

        self.current_deck = temp_deck

        # 应用顺序模式
        if order_mode == "random":
            random.shuffle(self.current_deck)

        # 存储其他模式设置
        self.question_mode = question_mode
        self.show_first_letter = show_first_letter
        self.retry_on_wrong = retry_on_wrong
        self.current_index = 0

    def start_review_mode(self) -> bool:
        """
        开始错题本复习模式。
        返回 True 如果成功开始，返回 False 如果没有错题。
        """
        if not self.wrong_words:
            print("No wrong words to review.")
            return False
            
        print(f"Starting review mode with {len(self.wrong_words)} words.")
        
        # 将当前牌组设置为错题本
        self.current_deck = list(self.wrong_words)
        
        # **核心逻辑：清空内存和硬盘上的错题本**
        # 答对的词将不再回来，答错的词会被重新添加
        self.wrong_words = set()
        self._save_wrong_words_to_disk()
        
        # 复习模式总是随机的
        random.shuffle(self.current_deck)
        self.current_index = 0
        return True

    def get_next_question(self) -> Optional[WordEntry]:
        """
        获取当前牌组中的下一个问题。
        如果牌组结束，返回 None。
        """
        if self.current_index >= len(self.current_deck):
            # 牌组结束
            return None
        
        return self.current_deck[self.current_index]

    def check_answer(self, user_input: str) -> bool:
        """
        检查用户答案是否正确，并自动推进到下一个单词。
        """
        if self.current_index >= len(self.current_deck):
            return False # 游戏已经结束

        current_word = self.current_deck[self.current_index]
        # 只取第一个逗号之前的部分，以防 CSV 中包含额外信息
        correct_answer = current_word.english.split(',')[0].strip()

        # 不区分大小写和首尾空格
        is_correct = (user_input.strip().lower() == correct_answer.lower())

        if not is_correct:
            # 答错了！添加到错题本并保存
            self.wrong_words.add(current_word)
            self._save_wrong_words_to_disk()

        # 无论对错，都推进到下一个单词
        self.current_index += 1

        return is_correct

    def skip_current_word(self) -> Optional[WordEntry]:
        """
        跳过当前单词，并将其计入错题本。
        返回被跳过的单词，如果游戏结束则返回 None。
        """
        if self.current_index >= len(self.current_deck):
            return None # 游戏已经结束

        current_word = self.current_deck[self.current_index]

        # 跳过的单词自动计入错题本
        self.wrong_words.add(current_word)
        self._save_wrong_words_to_disk()

        # 推进到下一个单词
        self.current_index += 1

        return current_word

    # --- *** 新增方法 1 *** ---
    def skip_without_penalty(self) -> Optional[WordEntry]:
        """
        跳过当前单词，并从错题本中移除（如果存在）。
        """
        if self.current_index >= len(self.current_deck):
            return None # 游戏已经结束

        current_word = self.current_deck[self.current_index]

        # 从错题本中移除（如果存在）
        if current_word in self.wrong_words:
            self.wrong_words.remove(current_word)
            self._save_wrong_words_to_disk()

        # 推进索引
        self.current_index += 1

        return current_word

    def clear_wrong_words_cache(self):
        """清空内存和硬盘上的所有错题。"""
        self.wrong_words = set()
        self._save_wrong_words_to_disk()
        print("Wrong words cache cleared.")

    def get_progress(self) -> tuple[int, int]:
        """
        返回当前进度 (当前索引, 总单词数)
        """
        return (self.current_index, len(self.current_deck))
        
    def get_wrong_word_count(self) -> int:
        """
        返回当前错题本中的单词数量
        """
        return len(self.wrong_words)
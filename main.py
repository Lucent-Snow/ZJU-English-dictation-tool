import sys
import re
import random
import json
import os
from typing import Optional, List

# 导入 PyQt6 的核心组件
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QComboBox, QRadioButton,
    QCheckBox, QScrollArea, QDockWidget, QButtonGroup, QMessageBox,
    QSizePolicy
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, pyqtSlot

# 导入我们自己的 "大脑" 和 "工人"
from model import DataLoader, WordEntry
from engine import GameEngine

class MainWindow(QMainWindow):
    """
    主窗口 (View)。
    它拥有 Engine 和 Loader 的实例，并负责所有UI渲染和事件处理。
    """
    def __init__(self):
        super().__init__()

        # 初始化数据加载器和游戏引擎
        try:
            self.loader = DataLoader(data_directory="./data")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"数据加载器初始化失败: {e}\n请确保 'data' 目录存在。")
            sys.exit(1)

        self.engine = GameEngine(self.loader)
        self.keybindings = self.load_keybindings()
        self.current_word: Optional[WordEntry] = None

        # 设置主窗口
        self.setWindowTitle("大英默写器 (app版)")
        self.setGeometry(100, 100, 1000, 700)

        # 初始化UI
        self.init_main_ui()
        self.init_settings_dock()
        self.populate_books_combo()
        self.update_review_button_count()

        # 创建工具栏
        self.toolbar = self.addToolBar("Main Toolbar")
        self.toolbar.setMovable(False)

        # 添加帮助按钮
        self.help_action = self.toolbar.addAction("帮助")
        self.help_action.triggered.connect(self.show_help_dialog)

        # 添加右侧设置切换按钮
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)

        self.toggle_settings_action = self.toolbar.addAction("隐藏设置")
        self.toggle_settings_action.triggered.connect(self.toggle_settings_panel)

        # 禁用输入框，直到游戏开始
        self.input_line.setEnabled(False)
        self.show()

    def init_main_ui(self):
        """设置中央的 "滚动日志" 和输入框"""
        
        # 可滚动的日志区域
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Arial", 14))
        self.log_area.setPlaceholderText("欢迎使用大英默写器！\n请在右侧面板选择词库并开始游戏。")

        # 单词输入行
        self.input_line = QLineEdit()
        self.input_line.setFont(QFont("Arial", 14))
        # 关键绑定：按回车键时，调用 self.submit_answer
        self.input_line.returnPressed.connect(self.submit_answer)

        # 中央布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.log_area, stretch=1) # stretch=1 使其填充主要空间
        main_layout.addWidget(self.input_line)

        # 设置中央窗口
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def load_keybindings(self) -> dict:
        """加载 keybindings.json。如果不存在则创建默认值。"""
        bindings_file = "keybindings.json"
        default_bindings = {
            "a": "action_skip_no_penalty",
            "/skip": "action_skip_no_penalty",
            "/clc": "action_clear_cache",
            "/clear": "action_clear_screen",
            "/review": "action_start_review"
        }

        if not os.path.exists(bindings_file):
            try:
                with open(bindings_file, 'w', encoding='utf-8') as f:
                    json.dump(default_bindings, f, indent=4)
                return default_bindings
            except Exception as e:
                print(f"无法创建默认 keybindings.json: {e}")
                return {}

        try:
            with open(bindings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载 keybindings.json 失败: {e}")
            return default_bindings

    def init_settings_dock(self):
        """设置可折叠的右侧停靠面板"""
        self.settings_dock = QDockWidget("设置", self)
        self.settings_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.settings_dock.setTitleBarWidget(QWidget())
        self.settings_dock.setFixedWidth(300)
        self.settings_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)

        settings_widget = QWidget()
        self.settings_layout = QVBoxLayout(settings_widget)

        # 书本选择
        self.settings_layout.addWidget(QLabel("1. 选择书本:"))
        self.book_combo = QComboBox()
        self.book_combo.currentTextChanged.connect(self.populate_units_checkboxes)
        self.settings_layout.addWidget(self.book_combo)

        # 单元选择
        self.settings_layout.addWidget(QLabel("2. 选择单元:"))
        self.unit_scroll_area = QScrollArea()
        self.unit_scroll_area.setWidgetResizable(True)
        self.unit_container = QWidget()
        self.unit_layout = QVBoxLayout(self.unit_container)
        self.unit_layout.addStretch()
        self.unit_scroll_area.setWidget(self.unit_container)
        self.settings_layout.addWidget(self.unit_scroll_area)
        self.unit_checkboxes: List[QCheckBox] = []

        # 内容过滤选项
        self.settings_layout.addWidget(QLabel("3. 选择内容:"))
        self.content_filter_group = QButtonGroup(self)
        self.radio_filter_all = QRadioButton("全部 (单词+短语)")
        self.radio_filter_words = QRadioButton("仅单词")
        self.radio_filter_phrases = QRadioButton("仅短语")
        self.radio_filter_all.setChecked(True)
        self.content_filter_group.addButton(self.radio_filter_all, 0)
        self.content_filter_group.addButton(self.radio_filter_words, 1)
        self.content_filter_group.addButton(self.radio_filter_phrases, 2)
        self.settings_layout.addWidget(self.radio_filter_all)
        self.settings_layout.addWidget(self.radio_filter_words)
        self.settings_layout.addWidget(self.radio_filter_phrases)

        # 顺序模式选项
        self.settings_layout.addWidget(QLabel("4. 选择顺序:"))
        self.order_mode_group = QButtonGroup(self)
        self.radio_order_seq = QRadioButton("顺序模式")
        self.radio_order_rand = QRadioButton("随机模式")
        self.radio_order_seq.setChecked(True)
        self.order_mode_group.addButton(self.radio_order_seq, 0)
        self.order_mode_group.addButton(self.radio_order_rand, 1)
        self.settings_layout.addWidget(self.radio_order_seq)
        self.settings_layout.addWidget(self.radio_order_rand)

        # 问题模式选项
        self.settings_layout.addWidget(QLabel("5. 选择模式:"))
        self.question_mode_group = QButtonGroup(self)
        self.radio_q_word = QRadioButton("单词模式 (中文 -> 英文)")
        self.radio_q_example = QRadioButton("例句模式 (例句填空)")
        self.radio_q_word.setChecked(True)
        self.question_mode_group.addButton(self.radio_q_word, 0)
        self.question_mode_group.addButton(self.radio_q_example, 1)
        self.settings_layout.addWidget(self.radio_q_word)
        self.settings_layout.addWidget(self.radio_q_example)

        # 提示选项
        self.settings_layout.addWidget(QLabel("6. 额外提示:"))
        self.cb_show_first_letter = QCheckBox("显示首字母提示")
        self.settings_layout.addWidget(self.cb_show_first_letter)

        # 错误重试选项
        self.settings_layout.addWidget(QLabel("7. 答题选项:"))
        self.cb_retry_on_wrong = QCheckBox("错误重试 (答错后继续显示当前单词)")
        self.settings_layout.addWidget(self.cb_retry_on_wrong)

        # 操作按钮
        self.start_button = QPushButton("开始游戏")
        self.start_button.clicked.connect(self.start_game)
        self.settings_layout.addWidget(self.start_button)

        self.review_button = QPushButton("复习错题 (0)")
        self.review_button.clicked.connect(self.start_review)
        self.settings_layout.addWidget(self.review_button)

        self.clear_wrong_button = QPushButton("清空错题本")
        self.clear_wrong_button.clicked.connect(self.clear_wrong_words)
        self.settings_layout.addWidget(self.clear_wrong_button)

        self.settings_layout.addStretch()
        self.settings_dock.setWidget(settings_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.settings_dock)

    # --- UI 填充和更新 ---

    def populate_books_combo(self):
        """(调用 Loader) 填充书本下拉框"""
        books = self.loader.get_available_books()
        if not books:
            QMessageBox.warning(self, "警告", "在 'data' 目录中未找到任何书本（子目录）。")
        self.book_combo.addItems(books)
        # 自动触发一次单元格加载
        self.populate_units_checkboxes()

    def populate_units_checkboxes(self):
        """(调用 Loader) 根据选择的书本，动态创建单元复选框"""
        # 1. 清空旧的复选框
        for cb in self.unit_checkboxes:
            self.unit_layout.removeWidget(cb)
            cb.deleteLater() # 释放内存
        self.unit_checkboxes = []

        # 2. 获取新数据
        current_book = self.book_combo.currentText()
        if not current_book:
            return
        units = self.loader.get_units_for_book(current_book)

        # 3. 创建新的复选框
        for unit_name in units:
            cb = QCheckBox(unit_name)
            # 插入到 "addStretch" 之前
            self.unit_layout.insertWidget(self.unit_layout.count() - 1, cb)
            self.unit_checkboxes.append(cb)

    def update_review_button_count(self):
        """(调用 Engine) 更新错题本按钮上的数字"""
        count = self.engine.get_wrong_word_count()
        self.review_button.setText(f"复习错题 ({count})")

    def append_to_log(self, message: str, color: str = "black"):
        """向滚动日志中添加一条带颜色的信息"""
        self.log_area.setTextColor(QColor(color))
        self.log_area.append(message)
        # 自动滚动到底部
        self.log_area.ensureCursorVisible()

    def _extract_chinese_hint(self, full_text: str) -> str:
        """
        (私有) 尝试从复杂的中文释义中提取核心中文提示。
        例如："1) ... object 演变；逐步发展"  -> "演变；逐步发展"
        """
        # 正则表达式：匹配所有中文汉字和常用的中文标点
        # 这将找到像 "演变；逐步发展" 或 "企业家" 这样的片段
        pattern = r'[\u4e00-\u9fa5；，。（）]+'
        matches = re.findall(pattern, full_text)

        if not matches:
            # 如果（意外地）一个中文字都没找到，
            # 我们就返回原始文本的前20个字符作为B计划
            return full_text[:20] + "..." if len(full_text) > 20 else full_text

        # 将所有匹配到的中文部分用 " / " 隔开
        # 例如："n. 演变 v. 发展" -> "演变 / 发展"
        return " / ".join(matches)

    def _get_clean_english(self, word: WordEntry) -> str:
        """
        (私有) 获取干净的英文单词（移除逗号后内容和隐藏字符）。
        用于确保答案比较和显示的一致性。
        """
        # 移除逗号及之后的内容
        english = word.english.split(',')[0].strip()
        return english

    @pyqtSlot()
    def toggle_settings_panel(self):
        """(C-V) 切换设置面板的可见性"""
        if self.settings_dock.isVisible():
            # 如果是可见的，就隐藏它
            self.settings_dock.hide()
            self.toggle_settings_action.setText("显示设置")
        else:
            # 如果是隐藏的，就显示它
            self.settings_dock.show()
            self.toggle_settings_action.setText("隐藏设置")

    @pyqtSlot()
    def show_help_dialog(self):
        """显示帮助和关于信息"""
        help_text = """
欢迎使用"大英默写器"！

## 作者
Lucent_Snow

## 功能
* **个性化词书**：支持对词书进行个性化修改（建议备份后删除所有专有名词）
* **可定制指令**: 在 `keybindings.json` 文件中自定义快捷键。
* **多种模式**: 自由组合内容、顺序、模式和提示。
* **错题本**: 自动记录答错的词，可通过 `/review` 或 `/clc` 管理。
* **例句填空**: 仿照小测的填空模式，由于技术原因，不支持词性变换，大家只需输入原型即可。

## 默认指令
* `/skip` 或 `a`: 跳过 (不计入错题)
* `/review`: 开始错题本复习
* `/clc`: 清空错题本
* `/clear`: 清空日志

## 其他
本软件完全开源，欢迎访问 GitHub 仓库获取源码和最新版本。
同时也欢迎大家自行定制功能。

祝你使用愉快！
"""
        QMessageBox.information(self, "帮助", help_text)

    # --- 游戏逻辑槽函数 (Slots) ---

    @pyqtSlot()
    def start_game(self):
        """(C-E) 用户点击 "开始游戏" 按钮"""
        # 1. 从 UI 收集设置
        book = self.book_combo.currentText()
        selected_units = [cb.text() for cb in self.unit_checkboxes if cb.isChecked()]

        # --- *** 这是关键修改 *** ---
        # 1. 获取内容过滤器
        content_id = self.content_filter_group.checkedId()
        filter_mode = "words_only" if content_id == 1 else ("phrases_only" if content_id == 2 else "all")

        # 2. 获取顺序模式
        order_id = self.order_mode_group.checkedId()
        order_mode = "random" if order_id == 1 else "sequential"

        # 3. 获取提问模式
        q_id = self.question_mode_group.checkedId()
        question_mode = "example" if q_id == 1 else "word"

        # 4. 获取首字母提示
        show_first_letter = self.cb_show_first_letter.isChecked()

        # 5. 获取错误重试
        retry_on_wrong = self.cb_retry_on_wrong.isChecked()
        # --- *** 修改结束 *** ---

        if not selected_units:
            QMessageBox.warning(self, "提示", "请至少选择一个单元！")
            return

        # 2. (核心) 通知 Engine 开始游戏
        self.engine.start_game(book, selected_units,
                             filter_mode, order_mode,
                             question_mode, show_first_letter, retry_on_wrong)

        # 3. 更新 UI
        self.log_area.clear()
        self.append_to_log(f"--- 游戏开始 ---", "blue")
        self.append_to_log(f"书本: {book}, 单元: {', '.join(selected_units)}")
        self.input_line.setEnabled(True)

        # 4. 提出第一个问题
        self.ask_next_question()

        # --- *** 新增代码 *** ---
        # 5. 自动隐藏设置面板
        self.settings_dock.hide()
        self.toggle_settings_action.setText("显示设置") # 更新顶部按钮的文本

    @pyqtSlot()
    def start_review(self):
        """(C-E) 用户点击 "复习错题" 按钮"""
        # 1. (核心) 通知 Engine 开始复习模式
        success = self.engine.start_review_mode()

        if not success:
            QMessageBox.information(self, "提示", "错题本是空的，太棒了！")
            return

        # --- *** 新增代码：为复习模式设置合理的默认值 *** ---
        # 无论用户当前面板设置是什么，复习时都强制使用以下设置
        self.engine.question_mode = "word"      # 强制使用 "单词模式"
        self.engine.show_first_letter = True  # 强制 "显示首字母" (复习时给点提示)
        # engine 的 order_mode 已经被 start_review_mode() 设为随机了
        # --- *** 修改结束 *** ---

        # 2. 更新 UI
        self.log_area.clear()
        self.append_to_log(f"--- 错题本复习开始 (单词模式, 显示首字母) ---", "green") # 更新提示
        self.update_review_button_count() # 更新按钮数字 (会变为 0)
        self.input_line.setEnabled(True)

        # 3. 提出第一个问题
        self.ask_next_question()

        # --- *** 新增代码 *** ---
        # 4. 自动隐藏设置面板
        self.settings_dock.hide()
        self.toggle_settings_action.setText("显示设置") # 更新顶部按钮的文本

    def ask_next_question(self):
        """(C-E) 向 Engine 请求下一个问题并显示 (V2 - 修复递归, V3 - 修复无限循环)"""
        # 使用一个循环来确保我们能找到一个有效的问题
        invalid_count = 0  # 统计跳过的无效单词数量
        total_words = len(self.engine.current_deck)  # 记录总单词数

        while True:
            # 1. (核心) 向 Engine 获取下一个单词
            self.current_word = self.engine.get_next_question()

            # 2. 检查游戏是否结束
            if self.current_word is None:
                self.append_to_log(f"\n--- 恭喜！本轮已全部完成！ ---", "blue")
                self.input_line.setEnabled(False)
                return  # 退出函数

            # 3. 检查当前单词是否 "有效"
            is_valid_question = True
            if self.engine.question_mode == "example":
                sentence = self.current_word.examples
                if not sentence or '[[' not in sentence:
                    # 这是一个无效的问题（在例句模式下）
                    is_valid_question = False

            # 4. 根据是否有效来决定是跳过还是提问
            if is_valid_question:
                # 找到了有效问题，跳出循环，继续提问
                break
            else:
                # 无效问题，手动推进索引（不计入错题本）
                self.engine.current_index += 1
                invalid_count += 1

                # --- *** 新增：检查是否所有单词都无效 *** ---
                if invalid_count >= total_words:
                    # 整个牌组都没有有效例句
                    self.append_to_log(f"\n--- 错误：当前牌组中没有有效的例句数据！ ---", "red")
                    self.append_to_log(f"请检查 CSV 文件中的 examples 列，确保包含 '[[' 标记。", "gray")
                    self.append_to_log(f"或切换到其他模式（如单词模式）继续学习。", "gray")
                    self.input_line.setEnabled(False)
                    return  # 结束游戏
                # --- *** 新增结束 *** ---

                # 循环将继续，get_next_question() 会基于新索引获取下一个单词

        # --- 提问逻辑 (只有在 break 之后才会执行) ---
        # 5. 根据设置动态构建提示
        progress = self.engine.get_progress()

        # 先提取中文提示
        clean_hint = self._extract_chinese_hint(self.current_word.chinese)

        # 决定基础提示语 (例句 或 中文)
        base_hint_is_example = False

        if self.engine.question_mode == "example":
            sentence = self.current_word.examples
            # 从英文单词中提取首字母（使用统一的清理方法）
            english_word = self._get_clean_english(self.current_word)
            first_letter = english_word.split(' ')[0][0].lower()

            # 处理多个例句：按分号分割并随机选择一个
            sentences = sentence.split('；')
            if len(sentences) > 1:
                # 随机选择一个例句
                sentence = random.choice(sentences)

            # 自定义替换函数：在 [[word]] 前加首字母（如果勾选），后加 (中文)
            def replace_with_hint(match):
                # 前面：显示首字母（如果勾选）或空
                prefix = f"{first_letter}" if self.engine.show_first_letter else ""
                # 后面：始终显示中文
                suffix = f"({clean_hint})"
                return f"{prefix}________{suffix}"

            # 执行替换
            blanked_sentence = re.sub(r'\[\[.*?\]\]', replace_with_hint, sentence)

            self.append_to_log(f"\n({progress[0]}/{progress[1]}) 例句填空:", "black")
            self.append_to_log(f"  {blanked_sentence}", "black")
            base_hint_is_example = True

        if not base_hint_is_example:
            # 单词模式
            self.append_to_log(f"\n({progress[0]}/{progress[1]}) 请输入:", "black")

        # 准备最终提示字符串
        final_hint_string = f"{clean_hint}"

        if self.engine.show_first_letter:
            english_word = self._get_clean_english(self.current_word)
            first_letter = english_word.split(' ')[0][0].lower()  # 仅短语的第一个词的首字母
            final_hint_string += f" (首字母: {first_letter})"

        # 显示最终提示
        if base_hint_is_example:
            # 例句模式下，不需要额外的提示行（因为已经包含在填空中了）
            pass
        else:
            # 单词模式下，中文和首字母是主要提示
            self.append_to_log(f"  {final_hint_string}", "black")

        # 清理和聚焦
        self.input_line.clear()
        self.input_line.setFocus()

    @pyqtSlot()
    def submit_answer(self):
        """
        用户在输入框中按下了回车键。
        自定义指令分发器
        """
        user_input = self.input_line.text().strip()

        # 检查输入是否为自定义指令
        if user_input in self.keybindings:
            action_name = self.keybindings[user_input]
            self.handle_action(action_name)
            self.input_line.clear() # 执行指令后清空
            return

        # 2. 如果不是指令，则作为答案处理 (原逻辑)
        if self.current_word is None:
            self.input_line.clear()
            return

        # 将答案交给 Engine 判断
        is_correct = self.engine.check_answer(user_input)

        # 根据 Engine 返回的结果更新 UI
        if is_correct:
            # 使用统一的清理方法显示正确答案
            correct_answer = self._get_clean_english(self.current_word)
            self.append_to_log(f"  ✅ 正确: {correct_answer}", "green")
            # 答对了才进入下一个问题
            self.ask_next_question()
        else:
            self.append_to_log(f"  ❌ 错误！", "red")
            self.append_to_log(f"    你输入了: {user_input}", "red")
            # 使用统一的清理方法显示正确答案
            correct_answer = self._get_clean_english(self.current_word)
            self.append_to_log(f"    正确答案: {correct_answer}", "gray")
            # 答错了，更新错题本按钮计数
            self.update_review_button_count()

            # 如果启用了错误重试，不进入下一个问题，而是继续显示当前问题
            if self.engine.retry_on_wrong:
                # 修复：回退索引以重试当前单词
                self.engine.current_index -= 1
                self.append_to_log(f"  请重试！", "blue")
                self.input_line.clear()
                self.input_line.setFocus()
            else:
                # 未启用错误重试，进入下一个问题
                self.ask_next_question()

    def handle_action(self, action_name: str):
        """
        根据 keybindings 执行对应的动作。
        """
        if not self.input_line.isEnabled() and action_name not in ["action_start_review", "action_clear_cache", "action_clear_screen"]:
            # 游戏未开始时，只允许少数几个动作
            self.append_to_log("游戏尚未开始。", "gray")
            return

        if action_name == "action_skip_no_penalty":
            # 你的新 "skip" 逻辑
            skipped_word = self.engine.skip_without_penalty() # 调用 new engine method
            if skipped_word:
                # 检查单词是否从错题本中移除了
                if skipped_word not in self.engine.wrong_words:
                    self.append_to_log(f"  ⏩ 已跳过并从错题本移除: {self._get_clean_english(skipped_word)}", "blue")
                else:
                    self.append_to_log(f"  ⏩ 已跳过: {self._get_clean_english(skipped_word)}", "gray")
                self.update_review_button_count()  # 更新错题本按钮计数
            self.ask_next_question()

        elif action_name == "action_clear_cache":
            # 你的 "/clc" 逻辑
            self.engine.clear_wrong_words_cache() # 调用 new engine method
            self.update_review_button_count()
            self.append_to_log("--- 错题本已清空 ---", "blue")

        elif action_name == "action_clear_screen":
            # 你的 "/clear" 逻辑
            self.log_area.clear()
            if self.current_word:
                self._reprint_current_question() # 重新打印当前问题
            else:
                self.log_area.setPlaceholderText("已清屏。请在右侧开始新游戏。")

        elif action_name == "action_start_review":
            self.start_review()

        else:
            self.append_to_log(f"未知的动作: '{action_name}'。请检查 keybindings.json。", "red")

    def _reprint_current_question(self):
        """
        (私有) 重新打印当前问题，用于 /clear 指令。
        这是 ask_next_question 的后半部分，但 *不* 推进索引。
        """
        if not self.current_word:
            return

        progress = self.engine.get_progress()

        # --- (此逻辑复制自 ask_next_question) ---
        base_hint_is_example = False

        if self.engine.question_mode == "example":
            sentence = self.current_word.examples
            if sentence and '[[' in sentence:
                blanked_sentence = re.sub(r'\[\[.*?\]\]', '_______', sentence)
                self.append_to_log(f"\n({progress[0]}/{progress[1]}) 例句填空:", "black")
                self.append_to_log(f"  {blanked_sentence}", "black")
                base_hint_is_example = True
            else:
                if sentence:
                    self.append_to_log(f"\n({progress[0]}/{progress[1]}) (例句未处理) 请输入:", "gray")
                else:
                    self.append_to_log(f"\n({progress[0]}/{progress[1]}) (无例句) 请输入:", "gray")

        if not base_hint_is_example:
            self.append_to_log(f"\n({progress[0]}/{progress[1]}) 请输入:", "black")

        clean_hint = self._extract_chinese_hint(self.current_word.chinese)
        final_hint_string = f"{clean_hint}"

        if self.engine.show_first_letter:
            english_word = self._get_clean_english(self.current_word)
            first_letter = english_word.split(' ')[0][0].lower()
            final_hint_string += f" (首字母: {first_letter})"

        if base_hint_is_example:
            self.append_to_log(f"  提示: {final_hint_string}", "darkGray")
        else:
            self.append_to_log(f"  {final_hint_string}", "black")
        # --- (复制结束) ---

        self.input_line.setFocus()

    @pyqtSlot()
    def clear_wrong_words(self):
        """清空错题本"""
        # 调用引擎的清空方法
        self.engine.wrong_words.clear()
        self.engine._save_wrong_words_to_disk()
        # 更新按钮显示
        self.update_review_button_count()
        QMessageBox.information(self, "提示", "错题本已清空！")

# --- 程序入口 ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())
"""
统一的路径解析层。

原程序里所有路径都是相对路径（"./data"、"keybindings.json"、"wrong_words.json"）。
用 Python 直接跑没问题，但打包成 .app 后双击启动时，工作目录是 "/"，
这些相对路径全部失效，程序启动即失败。

这里把两类路径分开：

- 只读资源（data/ 词库、默认 keybindings.json）：随程序分发，
  打包后从 app bundle 内部读取。
- 用户数据（wrong_words.json 错题本、用户自定义的 keybindings.json）：
  写到系统的用户数据目录，可写，且不会被程序更新覆盖。
  同时兼容旧版本：若程序目录里还留着旧版写的文件，首次运行会自动迁移过来。
"""

import os
import shutil
import sys

APP_SUPPORT_NAME = "大英默写器"


def is_frozen() -> bool:
    """是否运行在打包后的可执行文件里。"""
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> str:
    """只读资源根目录（内含 data/ 和 keybindings.json）。"""
    if is_frozen():
        # PyInstaller 运行时把随附数据放在 sys._MEIPASS 指向的目录
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    # 直接跑源码时，就是本文件所在目录
    return os.path.dirname(os.path.abspath(__file__))


def user_data_dir() -> str:
    """可写的用户数据目录（按各平台惯例选择）。"""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share"
        )

    path = os.path.join(base, APP_SUPPORT_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def _legacy_candidates(filename: str):
    """旧版本用相对路径存放用户数据，可能残留文件的位置。

    只看「工作目录」和「可执行文件所在目录」，不看随程序分发的资源目录——
    后者一定是安装包里的那份默认配置，不能当成用户数据。
    """
    dirs = [os.getcwd()]
    if is_frozen():
        dirs.append(os.path.dirname(sys.executable))

    seen = []
    for directory in dirs:
        candidate = os.path.join(directory, filename)
        if candidate not in seen:
            seen.append(candidate)
    return seen


def _migrate_legacy(filename: str, target: str) -> str:
    """target 不存在时，把旧版本留在程序目录里的同名文件搬过来。"""
    if os.path.exists(target):
        return target

    for legacy in _legacy_candidates(filename):
        if os.path.isfile(legacy):
            try:
                shutil.copyfile(legacy, target)
                print(f"已从旧位置迁移 {filename}: {legacy} -> {target}")
            except OSError as exc:
                print(f"迁移 {filename} 失败: {exc}")
            break
    return target


def data_directory() -> str:
    """词库根目录。"""
    return os.path.join(resource_dir(), "data")


def bundled_keybindings_file() -> str:
    """随程序分发的默认快捷键配置。"""
    return os.path.join(resource_dir(), "keybindings.json")


def user_keybindings_file() -> str:
    """用户可编辑的快捷键配置。"""
    return _migrate_legacy(
        "keybindings.json", os.path.join(user_data_dir(), "keybindings.json")
    )


def wrong_words_file() -> str:
    """错题本文件。"""
    return _migrate_legacy(
        "wrong_words.json", os.path.join(user_data_dir(), "wrong_words.json")
    )

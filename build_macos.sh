#!/bin/bash
# 在 macOS 上把本项目打包成可双击运行的 .app
#
# 用法：  bash build_macos.sh [安装目录]
# 默认安装目录：~/Applications
#
# 环境变量：
#   PYTHON_BIN  指定 Python 解释器，默认自动探测 python3.13 / 3.12 / 3.11 / python3
#   PIP_INDEX   指定 pip 源，例如 https://pypi.tuna.tsinghua.edu.cn/simple；默认用官方源

set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${1:-$HOME/Applications}"
APP_NAME="大英默写器"
BUNDLE_ID="com.github.Lucent-Snow.ZJU-English-dictation-tool"

# ---- 找 Python（PyQt6 需要 Python 3.9+）----
if [ -z "${PYTHON_BIN:-}" ]; then
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v "$candidate")"
      break
    fi
  done
fi
if [ -z "${PYTHON_BIN:-}" ]; then
  echo "错误：找不到 python3。请先安装 Python 3.9+，或用 PYTHON_BIN 指定解释器路径。" >&2
  exit 1
fi

# 只有显式设了 PIP_INDEX 才换源，不替使用者做地域性决定
PIP_ARGS=()
if [ -n "${PIP_INDEX:-}" ]; then
  PIP_ARGS=(-i "$PIP_INDEX")
fi

# ---- 全程在临时目录里构建，不污染源码树 ----
BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/zju-dict-build.XXXXXX")"
trap 'rm -rf "$BUILD_ROOT"' EXIT
VENV="$BUILD_ROOT/venv"

echo "==> Python: $PYTHON_BIN"
echo "==> 构建目录: $BUILD_ROOT"
echo "==> 创建虚拟环境"
"$PYTHON_BIN" -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip ${PIP_ARGS[@]+"${PIP_ARGS[@]}"}
echo "==> 安装依赖 (PyQt6 + PyInstaller)"
"$VENV/bin/python" -m pip install --quiet "PyQt6>=6.10.0" "pyinstaller>=6.0" ${PIP_ARGS[@]+"${PIP_ARGS[@]}"}

echo "==> 打包"
cd "$SRC_DIR"
# PYINSTALLER_CONFIG_DIR 指到临时目录：用独立的配置与二进制缓存，
# 不改动、也不依赖用户全局的 PyInstaller 配置。
PYINSTALLER_CONFIG_DIR="$BUILD_ROOT/cache" "$VENV/bin/pyinstaller" \
  --noconfirm --clean --windowed \
  --name "$APP_NAME" \
  --osx-bundle-identifier "$BUNDLE_ID" \
  --add-data "$SRC_DIR/data:data" \
  --add-data "$SRC_DIR/keybindings.json:." \
  --distpath "$BUILD_ROOT/dist" \
  --workpath "$BUILD_ROOT/build" \
  --specpath "$BUILD_ROOT" \
  main.py

BUILT_APP="$BUILD_ROOT/dist/$APP_NAME.app"
echo "==> 校验签名"
codesign --verify --deep --strict "$BUILT_APP"

echo "==> 安装到 $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
if [ -e "$INSTALL_DIR/$APP_NAME.app" ]; then
  # 覆盖旧版本前先整体移除，避免新旧文件混在一起破坏 bundle 结构
  if command -v trash >/dev/null 2>&1; then
    trash "$INSTALL_DIR/$APP_NAME.app"
  else
    rm -rf "$INSTALL_DIR/$APP_NAME.app"
  fi
fi
# 用 ditto 而不是 cp -R / rsync：ditto 会正确保留 bundle 内部的符号链接和扩展属性
ditto "$BUILT_APP" "$INSTALL_DIR/$APP_NAME.app"

echo "==> 最终校验"
codesign --verify --deep --strict "$INSTALL_DIR/$APP_NAME.app"
echo
echo "完成：$INSTALL_DIR/$APP_NAME.app"
echo "在 Finder 里双击即可运行，或执行：open \"$INSTALL_DIR/$APP_NAME.app\""

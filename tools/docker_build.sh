#!/usr/bin/env bash
# ============================================================================
# 在 kivy/buildozer 容器内执行的构建脚本（工作目录 = /home/user/hostcwd = 仓库根）。
#
# 背景：kivy/buildozer:latest 镜像的 venv Python 为 3.14.x，而 Kivy 2.x 只能在
# Python <=3.12 上构建（cython 0.29 依赖的 cgi 模块在 3.13+ 被移除），且 p4a 要求
# 运行环境 Python 版本与 buildozer.spec 钉版一致（否则报
# "python3 should have same version as hostpython3, x != y"）。
#
# 本脚本：
#   1. 打印容器内可用 Python 清单（诊断用）；
#   2. 自动选择 3.10 / 3.11 / 3.12 的 Python（找不到再用 apt 安装，最后回退 python3）；
#   3. 用选中的 Python 新建独立 venv，安装最新 buildozer + cython + pip<24；
#   4. 把 buildozer.spec 中 python3 钉版动态改为该 Python 的"确切版本"，
#      从构造上消除 hostpython3 版本不匹配；
#   5. 清理镜像预置的旧 python 构建产物（保留 SDK/NDK），再执行构建。
# ============================================================================
set -uo pipefail

echo "================ Python 版本清单（诊断） ================"
for p in /usr/bin/python3* /usr/local/bin/python3*; do
  if [ -x "$p" ]; then echo "  $p -> $("$p" --version 2>&1)"; fi
done

# ---------- 1. 选择 Python 3.10-3.12 ----------
PYBIN=""
for p in python3.12 python3.11 python3.10 python3; do
  if command -v "$p" >/dev/null 2>&1; then
    v="$("$p" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo bad)"
    case "$v" in
      3.10|3.11|3.12) PYBIN="$p"; break ;;
    esac
  fi
done

# ---------- 2. 找不到则尝试 apt 安装 ----------
if [ -z "$PYBIN" ]; then
  echo ">> 未发现 3.10-3.12，尝试 apt 安装 python3.12 ..."
  (apt-get update -qq && apt-get install -y -qq python3.12 python3.12-venv) >/dev/null 2>&1 \
    && PYBIN=python3.12 \
    || true
fi
if [ -z "$PYBIN" ]; then
  echo ">> 尝试 apt 安装 python3.10 ..."
  (apt-get update -qq && apt-get install -y -qq python3.10 python3.10-venv) >/dev/null 2>&1 \
    && PYBIN=python3.10 \
    || true
fi
if [ -z "$PYBIN" ]; then
  echo "WARN: 未找到 Python 3.10-3.12，回退到 python3（构建可能失败，请查看下方日志）"
  PYBIN=python3
fi
echo "== 使用构建 Python: $PYBIN -> $("$PYBIN" --version 2>&1) =="

# ---------- 3. 新建独立 venv 并安装工具链 ----------
"$PYBIN" -m venv /tmp/bz-venv
# 新 venv 内无 PEP 668 标记；先降 pip<24（兼容旧 p4a 内部 API），再装 buildozer/cython
/tmp/bz-venv/bin/pip install --upgrade --quiet "pip<24" buildozer cython || \
  /tmp/bz-venv/bin/pip install --upgrade --quiet --break-system-packages "pip<24" buildozer cython
/tmp/bz-venv/bin/python -m pip --version

# ---------- 4. 钉版与运行 Python 版本对齐 ----------
PYVER="$("$PYBIN" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
sed -i "s/python3==[0-9.]*/python3==$PYVER/" buildozer.spec
echo "== buildozer.spec requirements 已同步: python3==$PYVER =="
grep '^requirements' buildozer.spec

# ---------- 5. 清理镜像预置的旧 python 构建产物（保留 SDK/NDK） ----------
rm -rf /root/.buildozer/android/platform/build-* \
       /root/.buildozer/android/platform/python* \
       /root/.buildozer/android/platform/hostpython* 2>/dev/null || true
rm -rf /home/user/.buildozer/android/platform/build-* \
       /home/user/.buildozer/android/platform/python* \
       /home/user/.buildozer/android/platform/hostpython* 2>/dev/null || true

# ---------- 6. 构建 ----------
echo ">> 开始构建 ..."
echo y | /tmp/bz-venv/bin/buildozer -v android debug

# -*- coding: utf-8 -*-
"""牛门线分析 —— 程序入口。

Android 上由 python-for-android 运行本文件；桌面预览直接 `python main.py`。
"""
import os
import sys

# 确保项目根目录可被导入（桌面运行与 Android 均适用）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ui import NiumenApp  # noqa: E402


if __name__ == "__main__":
    NiumenApp().run()

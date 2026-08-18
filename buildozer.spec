# ============================================================================
# Buildozer 配置 —— 将 Kivy/KivyMD 应用打包为 Android APK
# 构建在 GitHub Actions 的 kivy/buildozer Docker 镜像中执行
# ============================================================================

[app]

# 应用信息
title = 牛门线
package.name = niumen
package.domain = org.niumen

# 源码目录与打包范围
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,otf,ttf,txt,json,md
source.exclude_dirs = tests,.github,.buildozer,bin,tools,__pycache__

# 版本
version = 1.0.0

# Python 依赖。
# 说明：不钉版本，让 Buildozer/p4a 按自带 recipe 的默认版本安装（kivy/kivymd/pillow 均有 recipe，
# requests 为纯 Python 走 pip），避免"requirements 版本与 recipe 版本不匹配"导致 CI 构建失败。
# 代码兼容 Kivy 2.2+/2.3+ 与 KivyMD 1.1.1+/1.2.0。
requirements = python3,kivy,kivymd,requests,pillow

# 屏幕方向与全屏
orientation = portrait
fullscreen = 0

# Android 配置
android.permissions = INTERNET
android.api = 33
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.private_storage = True

# 图标（由 tools/make_icon.ps1 生成）
icon.filename = %(source.dir)s/app/assets/icon.png

[buildozer]

log_level = 2
warn_on_root = 1

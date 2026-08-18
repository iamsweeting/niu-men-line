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
# kivy/kivymd 钉住社区验证过的兼容组合（避免 pip 解析器在 kivymd 1.2.0 + kivy 最新版
# 之间报 "Cannot install ... conflicting dependencies"）；requests/pillow 走 p4a recipe 默认。
# 代码兼容 Kivy 2.2+/2.3+ 与 KivyMD 1.1.1+/1.2.0。
requirements = python3,kivy==2.2.0,kivymd==1.1.1,requests,pillow

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

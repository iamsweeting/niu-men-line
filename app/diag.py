# -*- coding: utf-8 -*-
"""启动诊断工具：里程碑记录（logcat 打印 + 落盘 startup.log）与屏幕状态标签。

用于排查真机"黑屏 / 闪退"：每一步都打印并落盘，屏幕上显示进度文字，
卡在哪一步可直接截图反馈；文件可经手机文件管理器或 adb 读取。
"""
import os
import time

_START = time.time()
_status_label = None
_log_paths = []


def _log_files():
    """候选日志文件：外部应用目录（手机文件管理器可读）+ 应用私有目录。"""
    if not _log_paths:
        try:
            from android.storage import app_external_storage_path
            d = app_external_storage_path()
            if d:
                _log_paths.append(os.path.join(d, "startup.log"))
        except Exception:
            pass
        try:
            from kivy.app import App
            app = App.get_running_app()
            if app is not None:
                _log_paths.append(os.path.join(app.user_data_dir, "startup.log"))
        except Exception:
            pass
    return _log_paths


def status(msg, show_toast=True):
    """记录一条里程碑：打印（Android 上进入 logcat）、落盘、更新屏幕标签，
    并弹 Android Toast（即使 Kivy 窗口黑屏/未渲染也能看到进度）。"""
    line = "[牛门线][%6.1fs] %s" % (time.time() - _START, msg)
    print(line, flush=True)
    for p in _log_files():
        try:
            d = os.path.dirname(p)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
    try:
        if _status_label is not None:
            _status_label.text = "%s\n%s" % (msg, time.strftime("%H:%M:%S"))
    except Exception:
        pass
    if show_toast:
        _toast(msg)


def _toast(text):
    """Android Toast 悬浮提示：不依赖 Kivy 渲染，黑屏时也能看到进度。"""
    try:
        from android import mActivity
        from jnius import autoclass
        Toast = autoclass("android.widget.Toast")
        Toast.makeText(mActivity, "牛门线: " + text, Toast.LENGTH_LONG).show()
    except Exception:
        pass


def make_status_label():
    """创建屏幕状态标签（启动早期即可见；UI 构建完成后由应用重新置顶）。"""
    try:
        from kivy.core.window import Window
        from kivy.uix.label import Label
        from kivy.graphics import Color, Rectangle
        lb = Label(
            text="牛门线启动中…",
            font_size="18sp",
            color=(1, 1, 1, 1),
            halign="center",
            valign="middle",
        )
        with lb.canvas.before:
            Color(0, 0, 0, 0.75)
            lb._bg = Rectangle(pos=lb.pos, size=lb.size)
        lb.bind(
            pos=lambda o, *a: setattr(o._bg, "pos", o.pos),
            size=lambda o, *a: setattr(o._bg, "size", o.size),
        )
        Window.add_widget(lb)
        return lb
    except Exception:
        return None

# -*- coding: utf-8 -*-
"""牛门线分析 —— Kivy/KivyMD 移动端界面。"""
import os
import threading
import traceback
from datetime import date, datetime

from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.resources import resource_find
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.utils import get_color_from_hex

from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
try:  # KivyMD 1.1.x/1.2.x：MDSeparator 位于 kivymd.uix.card
    from kivymd.uix.card import MDSeparator
except ImportError:  # KivyMD 2.x：分隔线改名为 MDDivider（kivymd.uix.divider）
    from kivymd.uix.divider import MDDivider as MDSeparator
from kivymd.uix.spinner import MDSpinner
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar
try:
    from kivymd.uix.pickers.datepicker import MDDatePicker
except ImportError:  # KivyMD 1.1.x 的旧路径
    from kivymd.uix.picker import MDDatePicker

from . import api, config, indicator, interpreter
from .chart import DateAxis, NMLChart
from .diag import status as diag_status

CARD_RADIUS = [dp(14), dp(14), dp(14), dp(14)]
CARD_PADDING = [dp(14), dp(12), dp(14), dp(12)]
LEVEL_KIND_COLORS = {
    "压力": "#ffa726",
    "支撑": "#4dd0e1",
    "突破": "#ef5350",
    "提示": "#ffd166",
}


def _hex(col):
    return "#%02x%02x%02x" % (int(col[0] * 255), int(col[1] * 255), int(col[2] * 255))


def _fmt(v):
    return interpreter.fmt_price(v)


def _ensure_cjk_font():
    """注册中文字体（Kivy 默认 Roboto 不含中文）。

    优先使用打包的 Noto Sans SC（CI 下载）；缺失时尝试 Android 系统字体。
    """
    regular = bold = None
    p = resource_find(config.FONT_REGULAR)
    if p and os.path.exists(p):
        regular = p
        pb = resource_find(config.FONT_BOLD)
        bold = pb if pb and os.path.exists(pb) else None
    if not regular:
        for cand in ("/system/fonts/NotoSansCJK-Regular.ttc",
                     "/system/fonts/DroidSansFallback.ttf"):
            if os.path.exists(cand):
                regular = cand
                break
    if regular:
        try:
            LabelBase.register(name="Roboto", fn_regular=regular, fn_bold=bold or regular)
            LabelBase.register(name="CJK", fn_regular=regular, fn_bold=bold or regular)
        except Exception:  # noqa: BLE001
            pass
    return regular


class NiumenApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "牛门线分析"
        self.rows = []                 # 原始K线（升序）
        self.bars = []                 # 指标结果（与 rows 等长）
        self.version = config.VERSION_BASIC
        self.code = config.DEFAULT_CODE
        self.source = ""
        self.stock_name = ""
        self.sel_idx = -1              # 选中日在 bars 中的下标
        self._loading = False
        self._last_code = config.DEFAULT_CODE

    # ------------------------------------------------------------------
    # 构建界面
    # ------------------------------------------------------------------
    def build(self):
        diag_status("build() 开始")
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.primary_hue = "700"
        _ensure_cjk_font()
        diag_status("字体注册完成")
        self._build_screen()
        diag_status("界面构建完成")
        Clock.schedule_once(lambda dt: self.on_query(config.DEFAULT_CODE), 0.6)
        Clock.schedule_once(lambda dt: self._raise_status_label(), 0.1)
        self._start_watchdog()
        return self.screen

    def _build_screen(self):
        self.screen = MDScreen()

        # MDScreen 是 RelativeLayout 子类，直接把控件挂到 screen 上会按 (0,0)
        # 定位（屏幕左下）且被后加的 ScrollView 覆盖；因此先建一个垂直根布局，
        # 顶栏固定顶部，ScrollView 占据其余空间。
        root = MDBoxLayout(orientation="vertical")
        self.screen.add_widget(root)

        self.topbar = MDTopAppBar(
            title="牛门线分析",
            md_bg_color=get_color_from_hex("#12294a"),
            elevation=0,  # KivyMD 阴影着色器在 Adreno 驱动上崩溃（真机 SIGSEGV）
            right_action_items=[
                ["theme-light-dark", lambda x: self.toggle_theme()],
                ["refresh", lambda x: self.on_query(self._last_code)],
            ],
        )
        root.add_widget(self.topbar)

        body = ScrollView(do_scroll_x=False, bar_width=dp(4))
        box = MDBoxLayout(
            orientation="vertical",
            padding=[dp(12), dp(8), dp(12), dp(24)],
            spacing=dp(10),
            size_hint_y=None,
        )
        box.bind(minimum_height=box.setter("height"))
        body.add_widget(box)
        root.add_widget(body)

        self._build_search(box)
        self._build_info_card(box)
        self._build_chart_card(box)
        self._build_values_card(box)
        self._build_judgment_card(box)

        box.add_widget(MDLabel(
            text="数据来源：腾讯财经（默认）/ 新浪财经（备用）\n"
                 "指标仅供技术分析参考，不构成任何投资建议",
            font_style="Caption", theme_text_color="Hint",
            adaptive_height=True, halign="center",
        ))

        # 加载遮罩
        self.loader = FloatLayout()
        self.loader.add_widget(MDCard(
            size_hint=(1, 1), md_bg_color=(0, 0, 0, 0.45),
            radius=[0, 0, 0, 0], elevation=0,
        ))
        self.loader.add_widget(MDSpinner(
            size_hint=(None, None), size=(dp(46), dp(46)),
            pos_hint={"center_x": 0.5, "center_y": 0.5}, active=True,
        ))

    def _build_search(self, box):
        row = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(58), spacing=dp(8),
        )
        self.input_field = MDTextField(
            hint_text="输入代码 如 sh000852 / 600519 / HSTECH",
            size_hint=(1, None), height=dp(56),
        )
        row.add_widget(self.input_field)
        btn = MDRaisedButton(
            text="查询", size_hint=(None, None), width=dp(80), height=dp(48),
        )
        btn.bind(on_release=lambda x: self.on_query(self.input_field.text))
        row.add_widget(btn)
        box.add_widget(row)

        chips = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8),
        )
        for code, label in (("sh000852", "中证1000"),
                            ("sh600519", "贵州茅台"),
                            ("hstech", "HSTECH")):
            b = MDRaisedButton(
                text=label, size_hint_x=1, size_hint_y=None, height=dp(36),
            )
            b.bind(on_release=lambda x, c=code: self.on_query(c))
            chips.add_widget(b)
        box.add_widget(chips)

    def _build_info_card(self, box):
        self.info_card = MDCard(
            orientation="vertical",
            padding=CARD_PADDING, spacing=dp(2),
            radius=CARD_RADIUS, elevation=0, size_hint_y=None,  # 阴影在 Adreno 崩溃
        )
        self.info_card.bind(minimum_height=self.info_card.setter("height"))
        self.name_label = MDLabel(text="—", font_style="H6", adaptive_height=True)
        self.meta_label = MDLabel(
            text="—", font_style="Caption",
            theme_text_color="Secondary", adaptive_height=True,
        )
        self.info_card.add_widget(self.name_label)
        self.info_card.add_widget(self.meta_label)

        date_row = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8),
        )
        self.date_label = MDLabel(
            text="—", adaptive_height=True, size_hint_x=1, valign="middle",
        )
        date_btn = MDIconButton(
            icon="calendar", theme_icon_color="Custom",
            icon_color=get_color_from_hex("#8ab4f8"),
        )
        date_btn.bind(on_release=self.open_date_picker)
        date_row.add_widget(self.date_label)
        date_row.add_widget(date_btn)
        self.info_card.add_widget(date_row)
        box.add_widget(self.info_card)

    def _build_chart_card(self, box):
        self.chart_card = MDCard(
            orientation="vertical",
            padding=[dp(6), dp(10), dp(6), dp(6)], spacing=dp(2),
            radius=CARD_RADIUS, elevation=0, size_hint_y=None,  # 阴影在 Adreno 崩溃
        )
        self.chart_card.bind(minimum_height=self.chart_card.setter("height"))
        self.chart = NMLChart()
        self.date_axis = DateAxis()
        self.legend_row = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(26), spacing=dp(2),
        )
        self.chart_card.add_widget(self.chart)
        self.chart_card.add_widget(self.date_axis)
        self.chart_card.add_widget(self.legend_row)
        box.add_widget(self.chart_card)

    def _build_values_card(self, box):
        self.values_card = MDCard(
            orientation="vertical",
            padding=CARD_PADDING, spacing=dp(2),
            radius=CARD_RADIUS, elevation=0, size_hint_y=None,  # 阴影在 Adreno 崩溃
        )
        self.values_card.bind(minimum_height=self.values_card.setter("height"))
        self.close_label = MDLabel(
            text="—", font_style="H5", adaptive_height=True,
            theme_text_color="Custom", text_color=config.COLOR_UP,
        )
        self.values_label = MDLabel(
            text="", markup=True, font_style="Body1", adaptive_height=True,
        )
        self.values_card.add_widget(self.close_label)
        self.values_card.add_widget(self.values_label)
        box.add_widget(self.values_card)

    def _build_judgment_card(self, box):
        self.judgment_card = MDCard(
            orientation="vertical",
            padding=CARD_PADDING, spacing=dp(4),
            radius=CARD_RADIUS, elevation=0, size_hint_y=None,  # 阴影在 Adreno 崩溃
        )
        self.judgment_card.bind(minimum_height=self.judgment_card.setter("height"))
        self.verdict_label = MDLabel(
            text="结构判断：—", font_style="H6", adaptive_height=True,
            theme_text_color="Custom", text_color=config.COLOR_UP,
        )
        self.stage_label = MDLabel(text="阶段：—", font_style="Subtitle1", adaptive_height=True)
        self.summary_label = MDLabel(
            text="", markup=True, font_style="Body1",
            theme_text_color="Secondary", adaptive_height=True,
        )
        self.levels_label = MDLabel(
            text="", markup=True, font_style="Body2", adaptive_height=True,
        )
        self.judgment_card.add_widget(self.verdict_label)
        self.judgment_card.add_widget(self.stage_label)
        self.judgment_card.add_widget(MDSeparator())
        self.judgment_card.add_widget(self.summary_label)
        self.judgment_card.add_widget(self.levels_label)
        box.add_widget(self.judgment_card)

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def toggle_theme(self, *args):
        self.theme_cls.theme_style = (
            "Light" if self.theme_cls.theme_style == "Dark" else "Dark"
        )

    def on_query(self, code=None, *args):
        raw = (code or self.input_field.text or "").strip()
        if not raw:
            self._toast("请输入代码")
            return
        try:
            code = api.normalize_code(raw)
        except ValueError as e:
            self._toast(str(e))
            return
        self._last_code = code
        self.input_field.text = code
        self._set_loading(True)
        # 请求序号：快速连点时丢弃过期线程的返回，避免旧结果覆盖新结果
        self._req_seq = getattr(self, "_req_seq", 0) + 1
        seq = self._req_seq

        def work():
            try:
                res = api.fetch_klines(code)
                Clock.schedule_once(lambda dt: self._on_fetch_ok(code, res, seq), 0)
            except Exception as e:  # noqa: BLE001
                Clock.schedule_once(lambda dt, err=e: self._on_fetch_err(code, err, seq), 0)

        threading.Thread(target=work, daemon=True).start()

    def _on_fetch_ok(self, code, res, seq):
        if seq != self._req_seq:
            return  # 已有更新的请求，丢弃本次结果
        try:
            self._set_loading(False)
            self.code = code
            self.rows = res["rows"]
            self.source = res["source"]
            self.stock_name = res["name"] or code
            self.version = api.detect_version(code)
            self.bars = indicator.compute(self.rows, self.version)
            self.sel_idx = len(self.bars) - 1
            self._update_all()
            diag_status("数据加载与渲染完成")
            self._remove_status_label()
        except Exception:  # noqa: BLE001
            # Clock 回调里的异常会直接终止应用（Kivy 不会兜住），这里转成可见错误
            self._set_loading(False)
            msg = "数据处理失败（%s）：\n%s" % (code, traceback.format_exc())
            print("[牛门线] %s" % msg, file=sys.stderr)
            self._show_crash(msg)

    def _on_fetch_err(self, code, err, seq):
        if seq != self._req_seq:
            return  # 已有更新的请求，丢弃本次结果
        self._set_loading(False)
        self._toast(str(err))
        self.name_label.text = "查询失败：%s" % code
        self.meta_label.text = str(err)
        self.verdict_label.text = "结构判断：—"
        self.stage_label.text = "阶段：—"
        self.summary_label.text = ""
        self.levels_label.text = ""

    def open_date_picker(self, *args):
        if not self.bars:
            self._toast("请先查询代码")
            return
        sel = self.bars[self.sel_idx]
        dt = datetime.strptime(sel["date"], "%Y-%m-%d").date()
        first = datetime.strptime(self.bars[0]["date"], "%Y-%m-%d").date()
        dlg = MDDatePicker(
            year=dt.year, month=dt.month, day=dt.day,
            min_date=first, max_date=date.today(),
        )
        dlg.bind(on_save=self.on_date_save)
        dlg.open()

    def on_date_save(self, instance, value, date_range):
        target = value.strftime("%Y-%m-%d")
        idx = -1
        for i, b in enumerate(self.bars):
            if b["date"] <= target:
                idx = i
            else:
                break
        if idx < 0:
            self._toast("所选日期无数据")
            return
        self.sel_idx = idx
        self._update_all()

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------
    def _update_all(self):
        if self.sel_idx < 0 or not self.bars:
            return
        self._update_info()
        self._update_chart()
        self._update_values()
        self._update_judgment()

    def _update_info(self):
        b = self.bars[self.sel_idx]
        ver_name = config.VERSION_NAMES.get(self.version, self.version)
        cost_note = ""
        if self.version != config.VERSION_BASIC:
            basis = b.get("cost_basis", "estimate")
            cost_note = "（成交额口径）" if basis == "amount" else "（估算口径）"
        self.name_label.text = "%s  %s" % (self.stock_name or self.code, self.code)
        self.meta_label.text = "数据源：%s · 版本：%s%s" % (self.source or "—", ver_name, cost_note)
        self.date_label.text = "截至交易日：%s（点击日历切换日期）" % b["date"]

    def _update_chart(self):
        start = max(0, self.sel_idx - (config.DISPLAY_POINTS - 1))
        end = self.sel_idx
        keys = [
            ("NML", config.COLOR_NML, "nml"),
            ("QRL", config.COLOR_QRL, "qrl"),
            ("SMX", config.COLOR_SMX, "smx"),
        ]
        if self.version != config.VERSION_BASIC:
            keys += [
                ("CBX20", config.COLOR_CBX20, "cbx20"),
                ("CBX60", config.COLOR_CBX60, "cbx60"),
            ]
        lines = []
        for label, col, key in keys:
            lines.append((label, col, [self.bars[i][key] for i in range(start, end + 1)]))
        window = self.bars[start:end + 1]
        self.chart.set_data(window, lines, end - start)
        self.date_axis.set_dates([b["date"] for b in window])
        self._refresh_legend()

    def _refresh_legend(self):
        self.legend_row.clear_widgets()
        entries = [
            ("—NML", config.COLOR_NML),
            ("—QRL", config.COLOR_QRL),
            ("—SMX", config.COLOR_SMX),
        ]
        if self.version != config.VERSION_BASIC:
            entries += [
                ("—CBX20", config.COLOR_CBX20),
                ("—CBX60", config.COLOR_CBX60),
            ]
        for label, col in entries:
            self.legend_row.add_widget(MDLabel(
                text=label, font_style="Caption", size_hint_x=1,
                adaptive_height=True, theme_text_color="Custom",
                text_color=col, halign="center",
            ))

    def _update_values(self):
        b = self.bars[self.sel_idx]
        close = b["close"]
        chg = None
        if self.sel_idx > 0:
            prev = self.rows[self.sel_idx - 1]["close"]
            if prev:
                chg = (close - prev) / prev * 100.0
        txt = "收盘 %s" % _fmt(close)
        if chg is not None:
            txt += "    %s%.2f%%" % ("+" if chg >= 0 else "", chg)
        self.close_label.text = txt
        self.close_label.text_color = config.COLOR_UP if (chg or 0) >= 0 else config.COLOR_DOWN

        res = interpreter.interpret(b, self.version)
        keys = [
            ("nml", "NML 牛门线", config.COLOR_NML),
            ("qrl", "QRL 强阻力线", config.COLOR_QRL),
            ("smx", "SMX 生命线", config.COLOR_SMX),
        ]
        if self.version != config.VERSION_BASIC:
            keys += [
                ("cbx20", "CBX20 短期成本", config.COLOR_CBX20),
                ("cbx60", "CBX60 中期成本", config.COLOR_CBX60),
            ]
        rows_html = []
        for key, label, col in keys:
            v = b.get(key)
            if v is None:
                continue
            status, scol = res["flags"].get(key, ("—", (0.7, 0.7, 0.7, 1.0)))
            rows_html.append(
                "[color=%s]%s[/color]  %s   [color=%s]● %s[/color]"
                % (_hex(col), label, _fmt(v), _hex(scol), status)
            )
        self.values_label.text = "\n".join(rows_html)

    def _update_judgment(self):
        b = self.bars[self.sel_idx]
        res = interpreter.interpret(b, self.version)
        self.verdict_label.text = "结构判断：%s" % res["verdict"]
        self.verdict_label.text_color = res["verdict_color"]
        self.stage_label.text = "阶段：%s" % res["stage"]
        self.summary_label.text = res["summary"]
        lines = []
        for kind, label, value, note in res["levels"]:
            col = LEVEL_KIND_COLORS.get(kind, "#ffffff")
            lines.append(
                "[color=%s]●[/color] %s %s（%s）%s" % (col, kind, label, _fmt(value), note)
            )
        self.levels_label.text = "\n".join(lines)

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def _set_loading(self, on):
        if on and not self._loading:
            self.screen.add_widget(self.loader)
            self._loading = True
        elif not on and self._loading:
            self.screen.remove_widget(self.loader)
            self._loading = False

    def _toast(self, msg):
        try:
            from kivymd.toast import toast
            toast(msg)
        except Exception:  # noqa: BLE001
            print("[牛门线] %s" % msg)

    # ------------------------------------------------------------------
    # 启动诊断辅助（详见 app/diag.py）
    # ------------------------------------------------------------------
    def _raise_status_label(self):
        """UI 根控件覆盖了启动状态标签，把它重新置顶以便继续可见。"""
        try:
            from kivy.core.window import Window
            from . import diag
            if diag._status_label is not None and diag._status_label.parent is not None:
                Window.remove_widget(diag._status_label)
                Window.add_widget(diag._status_label)
        except Exception:  # noqa: BLE001
            pass

    def _remove_status_label(self):
        """数据加载成功后移除诊断标签。"""
        try:
            from kivy.core.window import Window
            from . import diag
            if diag._status_label is not None and diag._status_label.parent is not None:
                Window.remove_widget(diag._status_label)
        except Exception:  # noqa: BLE001
            pass

    def _start_watchdog(self):
        """每 10 秒 Toast+日志记录一次"事件循环存活"；若某步卡死，将停留在最后一条。"""
        def check(dt):
            diag_status("watchdog: 事件循环正常，运行 %.0fs" % dt)
            Clock.schedule_once(check, 10)
        Clock.schedule_once(check, 10)

    def _show_crash(self, msg):
        """把异常信息显示在界面浮层上，便于无 adb 时直接截图反馈。"""
        try:
            from kivy.uix.label import Label as KivyLabel
            from kivy.uix.scrollview import ScrollView
            overlay = MDCard(
                size_hint=(0.95, 0.8),
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                md_bg_color=(0.08, 0.08, 0.10, 0.96),
                elevation=0,  # 阴影在 Adreno 崩溃
            )
            sv = ScrollView()
            lb = KivyLabel(
                text="[b]程序异常[/b]\n\n%s" % msg,
                markup=True,
                font_size=dp(12),
                color=(1, 0.45, 0.45, 1),
                size_hint_y=None,
                padding=[dp(12), dp(12)],
            )
            lb.bind(width=lambda o, *a: setattr(o, "text_size", (o.width, None)))
            lb.bind(texture_size=lambda o, *a: setattr(o, "height", o.texture_size[1]))
            sv.add_widget(lb)
            overlay.add_widget(sv)
            self.screen.add_widget(overlay)
        except Exception:  # noqa: BLE001
            pass

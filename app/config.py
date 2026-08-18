# -*- coding: utf-8 -*-
"""牛门线全局配置与常量。

牛门线本质是「唐奇安通道 + ATR 波动率」的复合变形指标：
    NML（牛门线）  = REF(HHV(H,20),1) + 0.5 * ATR(14)
    QRL（强阻力线）= REF(HHV(H,20),1) + 1.0 * ATR(14)
    SMX（生命线）  = MA(C,10)
    CBX20/CBX60    = 20/60 日加权平均成本线（仅标的版 / 指数版）
"""

KLINE_COUNT = 320          # 拉取的K线根数（覆盖 60 日成本线 + 20 日高点 + 14 日ATR 所需）
DISPLAY_POINTS = 5         # 图表展示的交易日点数（含所选日）

# 版本标识
VERSION_BASIC = "basic"    # 基础主图版（3 线，通用：个股/指数/期货/海外代码均可）
VERSION_STOCK = "stock"    # 标的版（个股/期货，含成本线 CBX20/CBX60）
VERSION_INDEX = "index"    # 指数版（大盘指数，含成本线 CBX20/CBX60）

VERSION_NAMES = {
    VERSION_BASIC: "基础主图版",
    VERSION_STOCK: "标的版（成本线）",
    VERSION_INDEX: "指数版（成本线）",
}

# 牛门线参数（与通达信公式保持一致）
N = 20            # 唐奇安通道周期
M = 14            # ATR 周期
SMA10 = 10        # 生命线周期
CBX20_N = 20      # 20 日成本线周期
CBX60_N = 60      # 60 日成本线周期

# 图表配色（RGBA，Kivy 0~1）
COLOR_NML = (0.29, 0.62, 0.96, 1.0)      # 蓝：牛门线
COLOR_QRL = (1.00, 0.65, 0.15, 1.0)      # 橙：强阻力线
COLOR_SMX = (0.67, 0.30, 0.78, 1.0)      # 紫：生命线
COLOR_CBX20 = (0.15, 0.78, 0.85, 1.0)    # 青：20日成本
COLOR_CBX60 = (0.93, 0.93, 0.35, 1.0)    # 黄：60日成本

COLOR_UP = (0.94, 0.33, 0.31, 1.0)       # 红涨（中国市场习惯）
COLOR_DOWN = (0.30, 0.69, 0.39, 1.0)     # 绿跌

# 中文字体（CI 中由 tools/fetch_fonts.sh 下载；Kivy 默认 Roboto 不含中文）
FONT_REGULAR = "app/assets/fonts/NotoSansCJKsc-Regular.otf"
FONT_BOLD = "app/assets/fonts/NotoSansCJKsc-Bold.otf"

# 默认查询代码（中证1000 指数，指数版示例）
DEFAULT_CODE = "sh000852"

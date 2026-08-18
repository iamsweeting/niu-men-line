# 牛门线分析（NiuMen Line）

一款在 **Android 手机**上运行的股票技术分析小工具：输入股票/指数代码，自动选择对应版本的 **牛门线** 指标，
绘制最近 **5 个交易日** 的 K 线与牛门线（NML / QRL / SMX，标的版与指数版另含 20/60 日成本线），
并给出**可读性强**的文字判读（结构偏多/偏空、所处阶段、关键压力与支撑位）。

> 技术栈：Python + [Kivy](https://kivy.org) + [KivyMD](https://kivymd.readthedocs.io)（Material Design 界面）
> 打包：Buildozer 在 GitHub Actions 中自动构建 APK（本项目不在本地运行，全部构建在 GitHub 完成）

---

## 功能特性

- 📱 **移动端原生界面**：深色主题、卡片式布局、红涨绿跌 K 线、五色指标线图例
- 🔍 **任意代码输入**：支持 `sh000852`、`600519`、`HSTECH`、`hk00700`、`usAAPL` 等格式（6 位纯数字自动补前缀）
- 🧭 **版本自动选择**：根据代码自动匹配 基础主图版 / 标的版 / 指数版
- 📊 **5 个交易日窗口**：包含所选日在内绘制牛门线各线 + 当日 OHLC 蜡烛
- 📅 **指定日期查看**：日历选择任意交易日回看当时结构
- 📰 **文字判读**：结构判断徽章 + 阶段描述 + 概述段落 + 关键位（压力/支撑/回踩观察位）
- 🌐 **双数据源**：默认腾讯财经历史 K 线接口，失败自动切换新浪财经
- 🌗 **深浅主题**：顶栏一键切换

---

## 牛门线原理

牛门线本质是**唐奇安通道（Donchian Channel）+ ATR 波动率**的复合变形指标：

| 指标线 | 公式 | 含义 |
| --- | --- | --- |
| NML（牛门线） | `REF(HHV(H,20),1) + 0.5×ATR(14)` | 前 20 日最高价 + 0.5 倍平均真实波幅，突破入场 / 压力线 |
| QRL（强阻力线） | `REF(HHV(H,20),1) + 1.0×ATR(14)` | 前 20 日最高价 + 1 倍 ATR，强压力 / 止盈线 |
| SMX（生命线） | `MA(C,10)` | 10 日均线，趋势参考 / 止损线 |
| CBX20 / CBX60 | 20/60 日加权平均成本 | 标的版：`SUM(AMOUNT,N)/SUM(V,N)/100`；指数版：`SUM(C*V,N)/SUM(V,N)` |

其中 `TR1 = MAX(H-L, ABS(H-REF(C,1)), ABS(L-REF(C,1)))`，`ATRV = MA(TR1,14)`。
股价突破 NML 视为多头信号，跌破 SMX 视为趋势走弱。

### 版本自动选择规则

| 代码 | 示例 | 版本 |
| --- | --- | --- |
| `sh000xxx`（上证系列指数） | `sh000001` 上证指数、`sh000852` 中证1000 | 指数版 |
| `sz399xxx`（深证系列指数） | `sz399001` 深证成指、`sz399006` 创业板指 | 指数版 |
| A股个股（`sh60x`/`sz0x`/`sz3x`/`bj`） | `sh600519`、`sz300750` | 标的版 |
| 其他（港股/美股/期货/HSTECH 等） | `hk00700`、`usaapl`、`hstech` | 基础主图版 |

> 成本线口径说明：标的版优先使用**成交额口径**（腾讯 K 线数据含成交额字段时）；
> 若数据源未提供成交额，则按 `收盘价×成交量` 加权**估算**并在界面标注"（估算口径）"。
> 指数版始终使用 `C×V/V` 口径（与通达信指数公式一致）。

---

## 📲 在手机上安装（GitHub 自动打包）

1. 将本项目推送到你的 GitHub 仓库：

   ```bash
   git init
   git add .
   git commit -m "牛门线分析 v1.0"
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/niu-men-line.git
   git push -u origin main
   ```

2. 打开仓库 **Actions** 标签页，会看到 `Build Android APK` 工作流自动运行：
   - `Unit tests`：先跑指标/判读/解析单元测试（约 1 分钟）
   - `Build Android APK`：Buildozer（Docker）打包（首次约 30~60 分钟，之后有缓存会快很多）
   - 也可以手动点击 **Run workflow** 重新构建

3. 构建成功后，进入该次运行的 **Summary** 页面，在 **Artifacts** 处下载 `niumen-apk`，解压得到 `niumen-1.0.0-<arch>-debug.apk`。

4. 把 APK 传到手机（微信/网盘/数据线均可），点击安装，首次需允许 **"安装未知来源应用"**。

> APK 为 debug 签名，可直接安装使用。首次构建耗时较长属正常现象（需下载 Android SDK/NDK 与依赖）。

---

## 🖥 本地运行与测试（可选，开发用）

桌面预览（需要 Python 3.8+）：

```bash
pip install kivy==2.3.0 kivymd==1.2.0 requests
bash tools/fetch_fonts.sh     # 下载中文字体（Windows 可用 Git Bash / WSL）
python main.py
```

运行单元测试：

```bash
pip install pytest
python -m pytest tests -v
```

---

## 项目结构

```
niu-men-line/
├── main.py                    # 程序入口
├── buildozer.spec             # Buildozer 打包配置（APK 参数、依赖）
├── app/
│   ├── config.py              # 常量：版本、周期参数、配色
│   ├── api.py                 # 腾讯（默认）/ 新浪（备用）数据源 + 解析 + 版本识别
│   ├── indicator.py           # 牛门线指标计算（纯函数）
│   ├── interpreter.py         # 文字判读（纯函数）
│   ├── chart.py               # Canvas K 线图 + 指标线 + 日期轴
│   ├── ui.py                  # KivyMD 界面
│   └── assets/                # 图标、字体（字体由 CI 下载）
├── tests/                     # 单元测试（CI 中自动执行）
├── tools/
│   └── fetch_fonts.sh         # 下载 Noto Sans SC 中文字体
└── .github/workflows/
    └── build-apk.yml          # GitHub Actions：测试 + 打包 APK + 上传产物
```

---

## 常见问题

**Q：界面中文显示为方块？**
A：Kivy 默认字体不含中文。GitHub Actions 构建前会自动下载 Noto Sans SC 并打包进 APK；
若手动构建（非 CI）请先执行 `tools/fetch_fonts.sh`。

**Q：提示"获取数据失败"？**
A：请确认代码格式（如 `sh000852`、`600519`、`HSTECH`）；部分海外代码（如新加坡指数 HSTECH）
腾讯/新浪接口可能没有收录，属数据源覆盖范围问题。也请确认手机网络正常。

**Q：成本线数值与券商软件不一致？**
A：腾讯 K 线接口不含历史成交额时，成本线按 `收盘价×成交量` 估算，与通达信 `AMOUNT` 口径会有细微差异；
界面会标注"（估算口径）"。成交额口径下公式为 `SUM(AMOUNT,N)/SUM(V,N)/100`，与原文一致。

**Q：如何修改指标参数？**
A：修改 `app/config.py` 中的 `N`（唐奇安周期）、`M`（ATR 周期）、`SMA10`、`CBX20_N`、`CBX60_N` 后重新打包。

**Q：APK 内 Kivy / KivyMD 是什么版本？**
A：`buildozer.spec` 不钉版本，由构建镜像自带的 p4a recipe 决定（Kivy 2.2+/2.3+、KivyMD 1.1.1+/1.2.0），
代码对上述版本均兼容，这样可避免"requirements 与 recipe 版本不匹配"导致的构建失败。

**Q：首次构建太慢？**
A：首次需下载 SDK/NDK/依赖（约 30~60 分钟）；工作流已配置缓存，后续构建显著加快。

**Q：Buildozer 构建步骤失败？**
A：构建使用官方 `kivy/buildozer` Docker 镜像，docker run 命令**不要加 `--user` 参数**（镜像入口脚本
会以 root 启动并自动按宿主机 UID/GID 创建用户；加 `--user` 会报 `groupadd: Permission denied`）。
若因镜像更新导致兼容问题，可将 `.github/workflows/build-apk.yml` 中的 `kivy/buildozer:latest`
改为固定版本 `kivy/buildozer:1.5.0` 后重试。也可以在本地按官方文档走非 Docker 路径
（`pip install buildozer` + 系统依赖）构建。

**Q：手机安装时提示"未安装应用"或"解析包错误"？**
A：请确认下载的 APK 完整（解压 artifact 后安装），且手机架构为 arm64 或 armv7（默认同时支持）。
若需自定义图标或应用名，修改 `tools/make_icon.ps1` 与 `buildozer.spec` 后重新构建。

---

## 免责声明

本项目仅为技术指标（牛门线）的原理演示与个人学习工具，界面中的文字判读由程序按固定规则自动生成，
**不构成任何投资建议**。股市有风险，投资需谨慎。

数据来源：腾讯财经（web.ifzq.gtimg.cn）、新浪财经（quotes.sina.cn）。

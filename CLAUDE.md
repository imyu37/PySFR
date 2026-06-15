# CLAUDE.md — PySFR

基于 ISO 12233 标准的空间频率响应（SFR/MTF）测量工具。MATLAB `sfrmat5.m` 的 Python 移植，FreeSimpleGUI 桌面应用。

## 项目结构

```
PySFR/
├── GUI.py                  # 主程序入口 — FreeSimpleGUI 桌面界面
├── src/
│   ├── PySFR.py            # 核心：SFRCalculator 类 (615行)
│   ├── slantedgeMTF.py     # 倾斜边缘 MTF 计算 (备选实现)
│   └── test_sfr_comparison.py  # 算法对比测试
├── docs/
│   ├── 算法比较报告.md     # Python vs MATLAB 算法逐项对比
│   └── draft-email-to-peter-burns.md  # 致 Peter Burns 邮件草稿
├── images/                 # 测试用标准图像
├── data/                   # Excel 输出目录
├── ref/                    # 原始 MATLAB sfrmat5.m 参考源码
├── README.md              # 用户文档（中文）
├── README.en.md           # 用户文档（英文）
└── LICENSE                # MIT 许可证
```

## 红线 (不可违反)

- **禁止重新引入 Tkinter**：项目已在 v1.0.2 彻底移除 Tkinter，GUI 层**仅使用 FreeSimpleGUI**。不要 `import tkinter`。
- **`io=0` 是死路**：`calculate_sfr(io=0)` 返回 `status=1` 并提示使用 GUI.py。只有 `io=1` (非 GUI 模式) 有效。新代码不要新增 `io` 的其他取值。
- **ROI 选择用 matplotlib RectangleSelector**：这是 GUI.py 中**唯一保留的 matplotlib.widgets 用法**，在 `ROITool.select_roi()` 中。不要移除它或改用其他方案。
- **中文路径兼容**：图像加载用 `np.fromfile` + `cv2.imdecode`，不用 `cv2.imread`（不支持中文路径）。

## 关键命令

```bash
# 启动 GUI
python GUI.py

# 直接调用 SFR 计算 (非 GUI)
python -c "from src.PySFR import SFRCalculator; ..."

# 运行算法对比测试
python src/test_sfr_comparison.py

# 冒烟测试
python -c "from src.PySFR import SFRCalculator; c=SFRCalculator(); print('OK')"
```

## 架构要点

- **GUI 层** (`GUI.py`, 1011行)：`SFRGUI` 类管理界面生命周期；`ROITool` 类封装 matplotlib ROI 选择器。
  - `_update_preview(self, window, image, roi_coords=None)` — 统一的图像预览更新方法（v1.0.2 提取，消除 3 处重复）。
- **核心计算** (`src/PySFR.py`, 615行)：`SFRCalculator` 类实现完整算法流水线：
  - `calculate_sfr(io=1, del_input, a, npol, wflag)` — 主入口。返回 `(status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi)`。
  - 关键内部方法：`project2` (像素投影)、`findedge2` (加权边缘拟合)、`tukey`/`ahamming` (窗口函数)、`sampeff` (采样效率)。
- **依赖**：`numpy scipy matplotlib opencv-python FreeSimpleGUI Pillow`；可选 `pandas openpyxl`（Excel 导出）。

## 深入文档

| 文档 | 内容 |
|------|------|
| `README.md` (中文) | 用户手册：安装、使用方法、API 参数、更新日志、算法原理概述 |
| `README.en.md` (英文) | 同上，英文版 |
| `docs/算法比较报告.md` | Python vs MATLAB 算法逐项对比（投影/窗口/拟合/精度/性能） |

## 已知陷阱

- **Windows Tcl/Tk 路径**：GUI.py 在启动时硬编码 `C:\Program Files\Python313\tcl\tcl8.6` 设置 `TCL_LIBRARY`。如果 Python 版本不同需调整。
- **matplotlib 中文**：代码硬编码中文字体列表，跨平台时需确认字体存在。
- **日志文件**：运行后生成 `PySFR.log`（已在 `.gitignore` 中排除）。
- **Windows git index.lock 僵尸**：VSCode 的 `git commit --file -` 在 Windows 上可能留下无法自动清理的 `.git/index.lock`，导致所有 git 写操作失败。运行全局工具 `fix-git-lock` 一键修复（详见 `d:/YONG/2.Python/fix-git-lock`）。

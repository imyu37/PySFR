# py_sfrmat - Python 空间频率响应分析工具

基于 MATLAB 的 `sfrmat5.m` 移植的 Python 实现，用于计算图像系统的空间频率响应（SFR）。支持命令行和 GUI 两种操作模式。

## 项目结构

```
py_sfrmat/
├── sfrmat5.py          # 核心 SFR 计算类
├── GUI.py              # FreeSimpleGUI 界面
├── src/                # 源代码目录
│   ├── slantedgeMTF.py # 倾斜边缘 MTF 计算
│   └── test_sfr_comparison.py # 测试程序
├── docs/               # 文档目录
│   └── 算法比较报告.md # 算法比较报告
├── images/             # 测试图像目录
│   ├── ISO 12233-2023 chart.jpg
│   ├── Plan N 10x-1.bmp
│   ├── Test_edge1.tif
│   └── Test_edge1_mono.tif
└── README.md          # 项目文档
```

## 更新日志

### v1.0.2 (2026.4.17)
- 修复了 ESF 在边界位置的异常数据问题
- 优化了边缘投影算法，提高了精度
- 改进了 GUI 界面，完全基于 FreeSimpleGUI
- 修复了频率单位转换问题
- 增强了稳定性和可靠性

### v1.0.1 (2026.4.14)
- 初始 Python 版本发布
- 基于 sfrmat5.m 的完整功能移植
- 添加 FreeSimpleGUI 界面支持
- 改进的错误处理和日志记录
- 支持 Excel 数据导出

## 项目概述

`py_sfrmat` 是一个用于图像质量评估的 Python 工具，实现了 ISO 12233 标准中定义的空间频率响应（SFR）测量方法。该工具可以分析相机、镜头和其他成像系统的调制传递函数（MTF）。

### 主要特性

- **多通道支持**：支持 RGB 和亮度通道的独立分析
- **边缘检测**：自动检测和拟合图像中的边缘
- **超采样技术**：使用 4 倍超采样提高测量精度
- **窗口函数**：支持 Tukey 窗和汉明窗
- **双模式界面**：提供 FreeSimpleGUI 界面和命令行界面
- **ROI 选择工具**：交互式 ROI 区域选择
- **数据导出**：支持 Excel 格式数据导出
- **详细日志**：完整的日志记录和错误处理
- **跨平台支持**：Windows/Linux/macOS 兼容

## 安装要求

### Python 版本
- Python 3.7 或更高版本

### 依赖包
```bash
# 基础依赖
pip install numpy scipy matplotlib opencv-python

# GUI 界面依赖
pip install FreeSimpleGUI Pillow

# 可选：Excel 导出功能
pip install pandas openpyxl
```

### 主要依赖说明
- `numpy`: 数值计算和数组操作
- `scipy`: 科学计算（FFT、信号处理）
- `matplotlib`: 数据可视化和图表绘制
- `opencv-python`: 图像读取和处理
- `FreeSimpleGUI`: 图形用户界面
- `PIL` (Pillow): 图像处理支持
- `pandas`: Excel 数据导出（可选）
- `openpyxl`: Excel 文件支持（可选）

## 使用方法

### 1. GUI 模式（推荐）

```bash
# 启动 GUI 界面
python GUI.py
```

GUI 界面提供以下功能：
- 图像文件选择
- ROI 区域选择
- 参数配置界面
- 实时结果显示
- 数据导出功能

### 2. 命令行模式

```bash
# 基本命令行模式（交互式）
python sfrmat5.py
```

命令行模式会依次提示：
- 选择图像文件
- 选择 ROI 区域
- 输入采样间隔
- 显示分析结果
- 可选保存到 Excel

### 3. 程序化使用（API 调用）

```python
import numpy as np
from sfrmat5 import SFRCalculator

# 创建 SFR 计算器实例
sfr = SFRCalculator()

# 方法1：GUI 模式（自动文件选择和 ROI 选择）
status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = sfr.calculate_sfr()

# 方法2：非 GUI 模式（直接传入数据）
image_data = np.array(...)  # 你的图像数据
status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = sfr.calculate_sfr(
    io=1,                    # 非 GUI 模式
    del_input=0.01,          # 采样间隔（mm）
    a=image_data,            # 图像数据
    npol=5,                  # 多项式拟合阶数
    wflag=0                  # 窗口函数选择（0=Tukey, 1=Hamming）
)
```

## 输出结果说明

函数返回一个包含多个结果的元组：

- `status`: 处理状态（0=成功，1=失败）
- `dat`: SFR 数据矩阵 [频率, R, G, B, Lum]
- `e`: 采样效率数组
- `sfr50`: SFR 为 50% 时的频率值
- `fitme`: 边缘拟合参数
- `esf`: 边缘扩散函数数据
- `nbin`: 分箱因子
- `del2`: 超采样间隔
- `is_dpi`: 是否为 DPI 输入模式

## 算法原理

### 1. 边缘检测和拟合
- 使用一维导数检测边缘位置
- 多项式拟合边缘轮廓
- 自适应窗口函数优化边缘定位

### 2. 边缘扩散函数（ESF）计算
- 投影和分箱技术将 2D 边缘数据转换为 1D ESF
- 4 倍超采样提高空间分辨率

### 3. 线扩散函数（LSF）计算
- 对 ESF 进行微分得到 LSF
- 应用窗口函数减少频谱泄漏

### 4. 调制传递函数（MTF）计算
- 对 LSF 进行傅里叶变换得到 MTF
- 校正离散导数响应
- 归一化处理

## 示例图像

项目包含几个测试图像：

- `images/ISO 12233-2023 chart.jpg`: ISO 标准测试图
- `images/Plan N 10x-1.bmp`: 平面测试图像
- `images/Test_edge1.tif`: 边缘测试图像
- `images/Test_edge1_mono.tif`: 单通道边缘测试图像

## 参数配置

### 默认参数
```python
# 亮度权重（R, G, B）
guidefweight = np.array([0.213, 0.715, 0.072])

# 多项式拟合阶数
defnpol = 5

# 分箱因子
nbin = 4

# Tukey 窗参数
defalpha = 1.0
maxalpha = 1.0
minalpha = 0.5
```

### 可调参数
- `npol`: 边缘拟合的多项式阶数（1-5）
- `wflag`: 窗口函数选择（0=Tukey, 1=Hamming）
- `weight`: RGB 到亮度的转换权重
- `alpha`: Tukey 窗的形状参数

## 日志和调试

程序使用 Python 的 `logging` 模块提供详细的运行日志：

- 日志级别：INFO
- 输出：控制台和 `sfrmat5.log` 文件
- 编码：UTF-8

## 与 MATLAB 版本的比较

### 相同点
- 核心算法实现，包括精确的像素投影、窗口函数和边缘拟合
- 输入输出格式
- 参数设置和默认值
- 边缘检测和拟合方法
- SFR 计算流程

### 不同点
- Python 面向对象实现（SFRCalculator 类）
- 改进的错误处理和日志记录
- 双模式界面（FreeSimpleGUI + 命令行）
- 支持 Excel 数据导出
- 跨平台兼容性
- 独立的 ROI 选择工具类
- 修复了 ESF 在边界位置的异常数据问题
- 优化的边缘投影算法，提高了精度
- 现代化的 FreeSimpleGUI 界面

## 应用场景

1. **相机测试**: 评估相机系统的图像质量
2. **镜头评估**: 分析镜头的分辨率和对比度
3. **图像处理算法验证**: 测试图像处理算法对图像质量的影响
4. **科学研究**: 光学系统和成像质量的研究

## 注意事项

1. **图像质量**: 建议使用高质量、无压缩的图像文件
2. **边缘对比度**: 边缘对比度应大于 20% 以获得准确结果
3. **ROI 选择**: 选择包含清晰边缘的区域进行分析
4. **采样间隔**: 正确设置像素尺寸或 DPI 值

## 许可证

基于 Peter Burns 的 MATLAB 版本 `sfrmat5.m` 移植。

原始 MATLAB 代码版权信息：
- 作者: Peter Burns, pdburns@ieee.org
- 基于 sfrmat4，适配多项式边缘拟合
- 最后更新: 2023年2月27日
- 支持 ISO 12233 第4版

## 作者和贡献

- **原始 MATLAB 版本**: Peter Burns
- **Python 移植**: imyu37
- **项目维护**: wanyong_37@hotmail.com

## 参考文献

1. ISO 12233:2023 - Photography - Electronic still picture imaging - Resolution and spatial frequency responses
2. Burns, P.D., "Slanted-Edge MTF for Digital Camera and Scanner Analysis", IS&T's 2000 PICS Conference
3. sfrmat5.m MATLAB 实现文档
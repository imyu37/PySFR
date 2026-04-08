# py_sfrmat - Python 空间频率响应分析工具

基于 MATLAB 的 `sfrmat5.m` 移植的 Python 实现，用于计算图像系统的空间频率响应（SFR）。

## 更新日志

### v1.0.0 (2024)
- 初始 Python 版本发布
- 基于 sfrmat5.m 的完整功能移植
- 添加 GUI 界面支持
- 改进的错误处理和日志记录

## 项目概述

`py_sfrmat` 是一个用于图像质量评估的 Python 工具，实现了 ISO 12233 标准中定义的空间频率响应（SFR）测量方法。该工具可以分析相机、镜头和其他成像系统的调制传递函数（MTF）。

### 主要特性

- **多通道支持**：支持 RGB 和亮度通道的独立分析
- **边缘检测**：自动检测和拟合图像中的边缘
- **超采样技术**：使用 4 倍超采样提高测量精度
- **窗口函数**：支持 Tukey 窗和汉明窗
- **GUI 界面**：提供图形界面用于图像选择和 ROI 选择
- **详细日志**：完整的日志记录和错误处理

## 安装要求

### Python 版本
- Python 3.7 或更高版本

### 依赖包
```bash
pip install numpy scipy matplotlib opencv-python tkinter
```

### 主要依赖说明
- `numpy`: 数值计算和数组操作
- `scipy`: 科学计算（FFT、信号处理）
- `matplotlib`: 数据可视化和 GUI 界面
- `opencv-python`: 图像读取和处理
- `tkinter`: 图形用户界面（Python 标准库）

## 使用方法

### 基本使用

```python
from sfrmat5 import SFRCalculator

# 创建 SFR 计算器实例
sfr = SFRCalculator()

# 运行 SFR 分析（GUI 模式）
status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = sfr.calculate_sfr()
```

### 程序化使用（非 GUI 模式）

```python
import numpy as np
from sfrmat5 import SFRCalculator

# 加载图像数据
image_data = np.array(...)  # 你的图像数据

# 运行 SFR 分析
sfr = SFRCalculator()
status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = sfr.calculate_sfr(
    io=1,                    # 非 GUI 模式
    del_input=0.01,          # 采样间隔（mm）
    a=image_data,            # 图像数据
    npol=5,                  # 多项式拟合阶数
    wflag=0                  # 窗口函数选择（0=Tukey, 1=Hamming）
)
```

### 命令行运行

```bash
python sfrmat5.py
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
- 核心算法实现
- 输入输出格式
- 参数设置和默认值

### 不同点
- Python 面向对象实现
- 改进的错误处理
- 更详细的日志记录
- 现代化的 GUI 界面

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
- **Python 移植**: [您的姓名]
- **项目维护**: [您的联系信息]

## 参考文献

1. ISO 12233:2023 - Photography - Electronic still picture imaging - Resolution and spatial frequency responses
2. Burns, P.D., "Slanted-Edge MTF for Digital Camera and Scanner Analysis", IS&T's 2000 PICS Conference
3. sfrmat5.m MATLAB 实现文档

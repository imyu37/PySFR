"""
SFRMAT5 GUI界面
基于MATLAB sfrmat5.m的Python实现
"""

import io
import logging
import os
import platform

import cv2
import FreeSimpleGUI as sg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import RectangleSelector
from PIL import Image

from src.sfrmat5 import SFRCalculator

if platform.system() == "Windows":
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
else:
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("sfrmat5_gui.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class ROITool:
    """ROI选择工具"""

    def __init__(self, image):
        self.image = image
        self.roi_coords = None

    def select_roi(self):
        """显示ROI选择界面并返回ROI坐标"""
        fig, ax = plt.subplots(1, 1, figsize=(7, 5))

        # 归一化图像数据到[0, 1]范围以避免警告
        display_image = self.image.copy()
        if len(display_image.shape) == 3 and display_image.max() > 1:
            display_image = display_image / 255.0
        elif len(display_image.shape) == 2 and display_image.max() > 1:
            display_image = display_image / 255.0

        ax.imshow(display_image)
        ax.set_title("选择ROI区域 (拖动鼠标选择，按Enter确认)")

        def onselect(eclick, erelease):
            x1, y1 = int(eclick.xdata), int(eclick.ydata)
            x2, y2 = int(erelease.xdata), int(erelease.ydata)

            # 确保坐标顺序正确
            left, right = min(x1, x2), max(x1, x2)
            top, bottom = min(y1, y2), max(y1, y2)

            self.roi_coords = (left, top, right, bottom)

            # 绘制ROI矩形
            from matplotlib.patches import Rectangle

            roi_rect = Rectangle(
                (left, top),
                right - left,
                bottom - top,
                linewidth=2,
                edgecolor="red",
                facecolor="red",
                alpha=0.3,  # 设置透明度
            )
            ax.add_patch(roi_rect)
            fig.canvas.draw()

        # 创建矩形选择器
        rect_selector = RectangleSelector(
            ax,
            onselect,
            useblit=True,
            button=[1, 3],
            minspanx=5,
            minspany=5,
            spancoords="pixels",
            interactive=True,
        )

        def on_key_press(event):
            if event.key == "enter":
                plt.close(fig)

        fig.canvas.mpl_connect("key_press_event", on_key_press)
        plt.show()

        return self.roi_coords


def crop_to_roi(image, roi_coords):
    """根据ROI坐标裁剪图像"""
    if roi_coords is None:
        return image
    left, top, right, bottom = roi_coords
    return image[top:bottom, left:right]


class SFRMatGUI:
    """SFR计算器GUI界面"""

    def __init__(self):
        self.sg = sg
        self.calculator = SFRCalculator()

        # 设置主题
        sg.theme("LightBlue3")

        # 设置默认值
        self.defaults = {
            "sampling_interval": "1.0",
            "polynomial_order": "5",
            "window_type": "Tukey",
            "super_sampling": "4",
        }

        # 图像和分析变量
        self.current_image_path = None
        self.roi_coords = None
        self.results = None
        self.sfr_values = None  # 用于存储SFR关键值

    def create_layout(self):
        """创建GUI布局"""

        # 标题栏
        title_layout = [
            [
                sg.Text(
                    "SFRMAT5 - 空间频率响应分析",
                    font=("Microsoft Sans Serif", 16, "bold"),
                    justification="center",
                    expand_x=True,
                )
            ],
        ]

        # 图像控制区域
        image_control_layout = [
            [sg.Text("图像选择", font=("Microsoft Sans Serif", 11, "bold"))],
            [
                sg.Button("加载图像", size=(12, 1), key="-LOAD_IMAGE-"),
                sg.Button("选择ROI", size=(12, 1), key="-CHOOSE_ROI-"),
                sg.Button("清除ROI", size=(12, 1), key="-CLEAR_ROI-"),
            ],
            [sg.Text("状态: 未加载图像", key="-STATUS-", size=(50, 1))],
        ]

        # 参数设置区域
        params_layout = [
            [sg.Text("分析参数", font=("Microsoft Sans Serif", 11, "bold"))],
            [
                sg.Frame(
                    "",
                    [
                        [
                            sg.Column(
                                [
                                    [
                                        sg.Text("采样间隔:", size=(8, 1)),
                                        sg.InputText(
                                            self.defaults["sampling_interval"],
                                            key="-SAMPLING_INTERVAL-",
                                            size=(8, 1),
                                        ),
                                        sg.Text("(mm 或 dpi)", size=(9, 1)),
                                    ],
                                    [
                                        sg.Text("窗口类型:", size=(8, 1)),
                                        sg.Combo(
                                            ["Tukey", "Hamming"],
                                            default_value=self.defaults["window_type"],
                                            key="-WINDOW_TYPE-",
                                            size=(8, 1),
                                        ),
                                    ],
                                ]
                            ),
                            sg.VerticalSeparator(),
                            sg.Column(
                                [
                                    [
                                        sg.Text("多项式阶数:", size=(9, 1)),
                                        sg.InputText(
                                            self.defaults["polynomial_order"],
                                            key="-POLYNOMIAL_ORDER-",
                                            size=(5, 1),
                                        ),
                                    ],
                                    [
                                        sg.Text("超采样因子:", size=(9, 1)),
                                        sg.InputText(
                                            self.defaults["super_sampling"],
                                            key="-SUPER_SAMPLING-",
                                            size=(5, 1),
                                        ),
                                    ],
                                ]
                            ),
                        ]
                    ],
                )
            ],
        ]

        # 图像预览区域
        preview_layout = [
            [sg.Text("图像预览", font=("Microsoft Sans Serif", 11, "bold"))],
            [
                sg.Image(
                    key="-IMAGE_PREVIEW-", size=(400, 420), background_color="lightgray"
                )
            ],
            [sg.Text("ROI坐标:", key="-ROI_COORDS-", size=(50, 1))],
        ]

        # 分析控制区域
        analysis_layout = [
            [sg.Text("分析控制", font=("Microsoft Sans Serif", 11, "bold"))],
            [
                sg.Button(
                    "计算SFR",
                    size=(10, 1),
                    key="-CALCULATE_SFR-",
                    button_color=("white", "green"),
                ),
                sg.Button("显示SFR", size=(10, 1), key="-SHOW_PLOTS-"),
                sg.Button("显示多图", size=(10, 1), key="-SHOW_MULTI_PLOTS-"),
                sg.Button("保存数据", size=(10, 1), key="-SAVE_DATA-"),
            ],
        ]

        # 结果区域
        results_layout = [
            [sg.Text("分析结果", font=("Microsoft Sans Serif", 11, "bold"))],
            [
                sg.Multiline(
                    size=(80, 10),
                    key="-RESULTS_TEXT-",
                    disabled=True,
                    autoscroll=True,
                    font=("Microsoft Sans Serif", 9),
                )
            ],
        ]

        # 主布局
        layout = [
            title_layout,
            [
                sg.Column(
                    [
                        [sg.Frame("", image_control_layout)],
                        [sg.Frame("", params_layout)],
                        [sg.Frame("", analysis_layout)],
                        [sg.Frame("", results_layout)],
                    ],
                    size=(400, 500),
                ),
                sg.Column(
                    [
                        [sg.Frame("", preview_layout)],
                    ],
                    size=(400, 500),
                ),
            ],
            [sg.StatusBar("准备就绪", key="-STATUSBAR-", size=(80, 1))],
        ]

        return layout

    def load_image(self, window):
        """加载图像文件"""
        logger.info("打开文件对话框选择图像")

        # 使用FreeSimpleGUI文件对话框
        file_path = self.sg.popup_get_file(
            "选择图像文件",
            file_types=(
                ("图像文件", "*.png *.jpg *.jpeg *.tiff *.tif *.bmp *.gif"),
                ("所有文件", "*.*"),
            ),
            no_window=True,
            keep_on_top=True,
        )

        if file_path:
            try:
                logger.info(f"尝试加载图像: {file_path}")

                # 使用cv2加载图像
                image = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
                if image is None:
                    raise ValueError("无法读取图像文件")

                # 转换为float64
                image = np.array(image, dtype=np.float64)

                self.current_image_path = file_path
                self.calculator.image = image  # 临时存储图像用于预览

                # 更新状态
                window["-STATUS-"].update(
                    f"已加载: {os.path.basename(file_path)}, 形状: {image.shape}"
                )

                # 显示图像预览
                # 归一化图像数据到[0, 255]范围用于显示
                display_image = image.copy()
                if len(display_image.shape) == 3:
                    # RGB图像
                    display_image = (display_image / display_image.max() * 255).astype(
                        np.uint8
                    )
                else:
                    # 灰度图像
                    display_image = (display_image / display_image.max() * 255).astype(
                        np.uint8
                    )

                # 调整大小
                height, width = display_image.shape[:2]
                max_size = 400
                if width > height:
                    new_width = max_size
                    new_height = int(height * max_size / width)
                else:
                    new_height = max_size
                    new_width = int(width * max_size / height)

                if len(display_image.shape) == 3:
                    img_pil = Image.fromarray(display_image, "RGB")
                else:
                    img_pil = Image.fromarray(display_image, "L")

                img_resized = img_pil.resize(
                    (new_width, new_height), Image.Resampling.LANCZOS
                )

                img_byte_arr = io.BytesIO()
                img_resized.save(img_byte_arr, format="PNG")
                img_byte_arr = img_byte_arr.getvalue()

                window["-IMAGE_PREVIEW-"].update(data=img_byte_arr)
                window["-STATUSBAR-"].update("图像加载成功")

                logger.info("图像加载并显示成功")
                return True
            except Exception as e:
                logger.error(f"无法加载图像: {str(e)}")
                self.sg.popup_error(f"无法加载图像: {str(e)}")
                window["-STATUSBAR-"].update("图像加载错误")
                return False

        logger.debug("未选择图像文件")
        return False

    def choose_roi(self, window):
        """选择ROI区域"""
        if self.calculator.image is None:
            self.sg.popup_error("请先加载图像！")
            return

        try:
            roi_tool = ROITool(self.calculator.image)
            self.roi_coords = roi_tool.select_roi()

            if self.roi_coords:
                # 保存原始图像用于预览
                original_image = self.calculator.image.copy()

                # 裁剪图像到ROI用于分析
                cropped_image = crop_to_roi(self.calculator.image, self.roi_coords)

                # 更新预览 - 显示包含ROI方框的整张原始图
                display_image = original_image.copy()
                if len(display_image.shape) == 3:
                    display_image = (display_image / display_image.max() * 255).astype(
                        np.uint8
                    )
                else:
                    display_image = (display_image / display_image.max() * 255).astype(
                        np.uint8
                    )

                # 在图像上绘制ROI方框
                left, top, right, bottom = self.roi_coords

                # 绘制红色边框和填充（与ROI选择时保持一致）
                # 对于单色图像，需要转换为3通道才能显示红色
                if len(display_image.shape) == 2:
                    # 单色图像转换为3通道
                    display_image = cv2.cvtColor(display_image, cv2.COLOR_GRAY2RGB)

                # 先绘制红色填充（透明度30%）
                overlay = display_image.copy()
                cv2.rectangle(
                    overlay,
                    (left, top),
                    (right, bottom),
                    (255, 0, 0),
                    -1,  # -1表示填充
                )
                # 应用透明度
                cv2.addWeighted(overlay, 0.3, display_image, 0.7, 0, display_image)

                # 再绘制红色边框（线宽1）
                cv2.rectangle(
                    display_image, (left, top), (right, bottom), (255, 0, 0), 1
                )

                # 调整大小
                height, width = display_image.shape[:2]
                max_size = 400
                if width > height:
                    new_width = max_size
                    new_height = int(height * max_size / width)
                else:
                    new_height = max_size
                    new_width = int(width * max_size / height)

                if len(display_image.shape) == 3:
                    img_pil = Image.fromarray(display_image, "RGB")
                else:
                    img_pil = Image.fromarray(display_image, "L")

                img_resized = img_pil.resize(
                    (new_width, new_height), Image.Resampling.LANCZOS
                )

                img_byte_arr = io.BytesIO()
                img_resized.save(img_byte_arr, format="PNG")
                img_byte_arr = img_byte_arr.getvalue()

                window["-IMAGE_PREVIEW-"].update(data=img_byte_arr)
                window["-ROI_COORDS-"].update(f"ROI坐标: {self.roi_coords}")
                window["-STATUSBAR-"].update("ROI选择成功")

                # 更新分析器中的图像
                self.calculator.image = cropped_image

        except Exception as e:
            self.sg.popup_error(f"ROI选择失败: {str(e)}")
            window["-STATUSBAR-"].update("ROI选择错误")

    def clear_roi(self, window):
        """清除ROI选择"""
        if self.current_image_path and self.roi_coords:
            try:
                # 重新加载原始图像
                image = cv2.imread(self.current_image_path, cv2.IMREAD_UNCHANGED)
                image = np.array(image, dtype=np.float64)
                self.calculator.image = image

                # 更新预览
                display_image = image.copy()
                if len(display_image.shape) == 3:
                    display_image = (display_image / display_image.max() * 255).astype(
                        np.uint8
                    )
                else:
                    display_image = (display_image / display_image.max() * 255).astype(
                        np.uint8
                    )

                height, width = display_image.shape[:2]
                max_size = 400
                if width > height:
                    new_width = max_size
                    new_height = int(height * max_size / width)
                else:
                    new_height = max_size
                    new_width = int(width * max_size / height)

                if len(display_image.shape) == 3:
                    img_pil = Image.fromarray(display_image, "RGB")
                else:
                    img_pil = Image.fromarray(display_image, "L")

                img_resized = img_pil.resize(
                    (new_width, new_height), Image.Resampling.LANCZOS
                )

                img_byte_arr = io.BytesIO()
                img_resized.save(img_byte_arr, format="PNG")
                img_byte_arr = img_byte_arr.getvalue()

                window["-IMAGE_PREVIEW-"].update(data=img_byte_arr)
                window["-ROI_COORDS-"].update("ROI坐标: 无")
                self.roi_coords = None
                window["-STATUSBAR-"].update("ROI已清除")

            except Exception as e:
                self.sg.popup_error(f"无法清除ROI: {str(e)}")

    def calculate_sfr_values(self, dat, target_values):
        """计算指定SFR值对应的频率"""
        if dat is None or len(dat) == 0:
            return None

        sfr_values = {}
        num_channels = dat.shape[1] - 1  # 减去频率列

        for target in target_values:
            sfr_values[target] = []

            for channel in range(num_channels):
                # 查找SFR等于或接近目标值的频率
                sfr_data = dat[:, channel + 1]
                freq_data = dat[:, 0]

                # 找到最接近目标值的点
                idx = np.argmin(np.abs(sfr_data - target))

                if sfr_data[idx] >= target - 0.05:  # 允许一定的误差范围
                    # 使用线性插值得到更精确的值
                    if idx > 0 and idx < len(sfr_data) - 1:
                        # 三点插值
                        x1, x2, x3 = freq_data[idx - 1 : idx + 2]
                        y1, y2, y3 = sfr_data[idx - 1 : idx + 2]

                        # 使用抛物线插值
                        if y1 != y2 and y2 != y3:
                            # 计算抛物线参数
                            denom = (x1 - x2) * (x1 - x3) * (x2 - x3)
                            a = (
                                x3 * (y2 - y1) + x2 * (y1 - y3) + x1 * (y3 - y2)
                            ) / denom
                            b = (
                                x3 * x3 * (y1 - y2)
                                + x2 * x2 * (y3 - y1)
                                + x1 * x1 * (y2 - y3)
                            ) / denom
                            c = (
                                x2 * x3 * (x2 - x3) * y1
                                + x3 * x1 * (x3 - x1) * y2
                                + x1 * x2 * (x1 - x2) * y3
                            ) / denom

                            # 解方程 a*x^2 + b*x + c = target
                            discriminant = b * b - 4 * a * (c - target)
                            if discriminant >= 0:
                                root1 = (-b + np.sqrt(discriminant)) / (2 * a)
                                root2 = (-b - np.sqrt(discriminant)) / (2 * a)

                                # 选择在范围内的根
                                valid_roots = [
                                    r for r in [root1, root2] if x1 <= r <= x3
                                ]
                                if valid_roots:
                                    sfr_values[target].append(min(valid_roots))
                                else:
                                    sfr_values[target].append(freq_data[idx])
                            else:
                                sfr_values[target].append(freq_data[idx])
                        else:
                            # 线性插值
                            if sfr_data[idx] > target:
                                if idx > 0:
                                    x1, x2 = freq_data[idx - 1], freq_data[idx]
                                    y1, y2 = sfr_data[idx - 1], sfr_data[idx]
                                    freq = x1 + (target - y1) * (x2 - x1) / (y2 - y1)
                                    sfr_values[target].append(freq)
                                else:
                                    sfr_values[target].append(freq_data[idx])
                            else:
                                sfr_values[target].append(freq_data[idx])
                    else:
                        sfr_values[target].append(freq_data[idx])
                else:
                    sfr_values[target].append(0.0)

        return sfr_values

    def display_results(self, window, results):
        """在结果区域显示分析结果"""
        status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = results

        if status != 0 or dat is None:
            result_str = "SFR计算失败"
        else:
            # 计算SFR30和SFR10的值
            target_values = [0.5, 0.3, 0.1]  # SFR50, SFR30, SFR10
            sfr_values = self.calculate_sfr_values(dat, target_values)

            # 构建结果字符串
            result_str = f"""SFR分析结果
{"=" * 50}

基本参数:
- 状态: {"成功" if status == 0 else "失败"}
- 合并因子: {nbin}
- 采样间隔: {del2:.4f}
- 频率单位: {"cycles/pixel" if is_dpi else "cycles/mm"}

关键指标:
- SFR50: {sfr50:.4f}
"""

            # 添加SFR30和SFR10的值
            if sfr_values and 0.3 in sfr_values and len(sfr_values[0.3]) > 0:
                sfr30 = sfr_values[0.3][-1]  # 使用亮度通道的值
                result_str += f"- SFR30: {sfr30:.4f}\n"

            if sfr_values and 0.1 in sfr_values and len(sfr_values[0.1]) > 0:
                sfr10 = sfr_values[0.1][-1]  # 使用亮度通道的值
                result_str += f"- SFR10: {sfr10:.4f}\n"

            result_str += "\n采样效率:\n"

            # 添加各通道的采样效率
            channel_names = ["R", "G", "B", "Lum"]
            if e is not None and e.shape[1] > 0:
                # 对于单色图像，显示为Lum通道的采样效率
                if e.shape[1] == 1:
                    result_str += f"- Lum: {e[0, 0]:.1f}%\n"
                else:
                    for i in range(min(e.shape[1], len(channel_names))):
                        result_str += f"- {channel_names[i]}: {e[0, i]:.1f}%\n"

        window["-RESULTS_TEXT-"].update(result_str)
        self.results = results
        self.sfr_values = sfr_values  # 保存用于图表显示

    def run(self):
        """启动GUI事件循环"""
        # 创建窗口
        layout = self.create_layout()
        window = sg.Window("SFRMAT5", layout, size=(850, 600), resizable=False)

        # 事件循环
        while True:
            event, values = window.read()

            if event == sg.WIN_CLOSED:
                break

            elif event == "-LOAD_IMAGE-":
                self.load_image(window)

            elif event == "-CHOOSE_ROI-":
                self.choose_roi(window)

            elif event == "-CLEAR_ROI-":
                self.clear_roi(window)

            elif event == "-CALCULATE_SFR-":
                if self.calculator.image is None:
                    self.sg.popup_error("请先加载图像！")
                    continue

                try:
                    # 获取参数
                    sampling_interval = float(values["-SAMPLING_INTERVAL-"])
                    polynomial_order = int(values["-POLYNOMIAL_ORDER-"])
                    window_type = 1 if values["-WINDOW_TYPE-"] == "Hamming" else 0
                    super_sampling = int(values["-SUPER_SAMPLING-"])

                    # 设置参数
                    self.calculator.defnpol = polynomial_order
                    self.calculator.nbin = super_sampling

                    window["-STATUSBAR-"].update("正在计算SFR...")

                    # 执行SFR计算
                    results = self.calculator.calculate_sfr(
                        io=1,  # 非GUI模式
                        del_input=sampling_interval,
                        a=self.calculator.image,
                        npol=polynomial_order,
                        wflag=window_type,
                    )

                    self.display_results(window, results)
                    self.sg.popup("成功", "SFR计算完成！")
                    window["-STATUSBAR-"].update("计算完成")

                except Exception as e:
                    self.sg.popup_error(f"SFR计算失败: {str(e)}")
                    window["-STATUSBAR-"].update("计算错误")

            elif event == "-SHOW_PLOTS-":
                if self.results is None:
                    self.sg.popup_error("暂无结果可用。请先运行分析。")
                    continue

                try:
                    status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = self.results

                    if status == 0 and dat is not None:
                        # 绘制SFR结果图表
                        colors = ["red", "green", "blue", "black"]
                        num_channels = dat.shape[1] - 1

                        plt.figure(figsize=(7, 5))

                        # 判断是否为单色图像（只有1个通道）
                        is_monochrome = num_channels == 1

                        # 通道名称映射
                        channel_names = ["R", "G", "B", "Lum"]

                        for i in range(num_channels):
                            # 使用通道名称而不是通道编号
                            # 对于单色图像，显示为Lum通道
                            if is_monochrome:
                                channel_name = "Lum"
                            else:
                                channel_name = (
                                    channel_names[i]
                                    if i < len(channel_names)
                                    else f"通道{i}"
                                )
                            plt.plot(
                                dat[:, 0],
                                dat[:, i + 1],
                                color=colors[i % len(colors)],
                                label=channel_name
                                if not is_monochrome
                                else "",  # 单色时不显示图例
                            )

                        # 对于彩色图像，只绘制不带marker的Lum通道（避免重复）
                        if num_channels > 1:
                            # 检查是否已经有Lum通道的曲线
                            has_lum_curve = False
                            for i in range(num_channels):
                                if i < len(channel_names) and channel_names[i] == "Lum":
                                    has_lum_curve = True
                                    break

                            # 如果没有Lum通道的曲线，则绘制散点
                            if not has_lum_curve:
                                plt.scatter(
                                    dat[:, 0],
                                    dat[:, -1],
                                    s=40,
                                    marker="o",
                                    facecolors="none",
                                    edgecolors="black",
                                    label="Lum"
                                    if not is_monochrome
                                    else "",  # 单色时不显示图例
                                )

                        # 设置x轴标签
                        if is_dpi:
                            plt.xlabel("频率(cycles/pixel)")
                        else:
                            plt.xlabel("频率(cycles/mm)")

                        plt.xlim(0, None)
                        plt.ylim(0, 1)
                        plt.ylabel("SFR")
                        plt.title("空间频率响应")

                        # 添加SFR关键值标注
                        if hasattr(self, "sfr_values") and self.sfr_values:
                            sfr_text = "SFR关键值:\n"

                            # SFR50标注
                            if 0.5 in self.sfr_values and len(self.sfr_values[0.5]) > 0:
                                sfr50_val = self.sfr_values[0.5][-1]  # 亮度通道
                                sfr_text += f"SFR50: {sfr50_val:.3f}\n"

                            # SFR30标注
                            if 0.3 in self.sfr_values and len(self.sfr_values[0.3]) > 0:
                                sfr30_val = self.sfr_values[0.3][-1]  # 亮度通道
                                sfr_text += f"SFR30: {sfr30_val:.3f}\n"

                            # SFR10标注
                            if 0.1 in self.sfr_values and len(self.sfr_values[0.1]) > 0:
                                sfr10_val = self.sfr_values[0.1][-1]  # 亮度通道
                                sfr_text += f"SFR10: {sfr10_val:.3f}\n"

                            # 在右上角添加文本框
                            plt.text(
                                0.98,
                                0.98,
                                sfr_text,
                                transform=plt.gca().transAxes,
                                horizontalalignment="right",
                                verticalalignment="top",
                                bbox=dict(
                                    boxstyle="round", facecolor="white", alpha=0.8
                                ),
                                fontsize=9,
                            )

                        # 添加采样效率数据（移到左下角）
                        if e is not None and e.shape[1] > 0:
                            channel_names = ["R", "G", "B", "Lum"]
                            text_str = "采样效率:\n"
                            # 对于单色图像，显示为Lum通道的采样效率
                            if e.shape[1] == 1:
                                text_str += f"Lum: {e[0, 0]:.1f}%\n"
                            else:
                                for i in range(min(e.shape[1], len(channel_names))):
                                    text_str += f"{channel_names[i]}: {e[0, i]:.1f}%\n"

                            plt.text(
                                0.02,
                                0.02,
                                text_str,
                                transform=plt.gca().transAxes,
                                horizontalalignment="left",
                                verticalalignment="bottom",
                                bbox=dict(
                                    boxstyle="round", facecolor="white", alpha=0.8
                                ),
                                fontsize=9,
                            )

                        plt.legend()
                        plt.grid(True)
                        plt.tight_layout()
                        plt.show()

                        window["-STATUSBAR-"].update("图表已显示")
                    else:
                        self.sg.popup_error("无有效结果可显示")

                except Exception as e:
                    self.sg.popup_error(f"无法显示图表: {str(e)}")

            elif event == "-SHOW_MULTI_PLOTS-":
                if self.results is None:
                    self.sg.popup_error("暂无结果可用。请先运行分析。")
                    continue

                try:
                    status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = self.results

                    if status == 0 and dat is not None:
                        # 创建2行2列的图表布局
                        fig, axes = plt.subplots(2, 2, figsize=(8.5, 5.5))
                        fig.suptitle("SFR分析结果", fontsize=14)

                        # 1. 绘制ESF（边扩散函数）- 左上
                        if esf is not None and len(esf) > 0:
                            # 如果有多个通道，显示第一个通道的ESF
                            if len(esf.shape) > 1:
                                esf_plot = esf[:, 0]  # 使用第一个通道
                            else:
                                esf_plot = esf

                            x_esf = np.arange(len(esf_plot))
                            axes[0, 0].plot(x_esf, esf_plot, "b-", linewidth=2)
                            axes[0, 0].set_xlabel("像素位置", fontsize=10)
                            axes[0, 0].set_ylabel("强度", fontsize=10)
                            axes[0, 0].set_title("边扩散函数 (ESF)", fontsize=12)
                            axes[0, 0].set_xlim(0, None)
                            axes[0, 0].set_ylim(0, None)
                            axes[0, 0].grid(True)
                        else:
                            axes[0, 0].text(
                                0.5,
                                0.5,
                                "无ESF数据",
                                ha="center",
                                va="center",
                                transform=axes[0, 0].transAxes,
                            )
                            axes[0, 0].set_title("边扩散函数 (ESF)", fontsize=12)

                        # 2. 绘制LSF（线扩散函数）- 右上
                        if esf is not None and len(esf) > 0:
                            # 计算LSF（ESF的导数）
                            if len(esf.shape) > 1:
                                esf_for_lsf = esf[:, 0]  # 使用第一个通道
                            else:
                                esf_for_lsf = esf

                            # 计算导数作为LSF
                            lsf = np.gradient(esf_for_lsf)
                            x_lsf = np.arange(len(lsf))
                            axes[0, 1].plot(x_lsf, lsf, "r-", linewidth=2)
                            axes[0, 1].set_xlabel("像素位置", fontsize=10)
                            axes[0, 1].set_ylabel("导数", fontsize=10)
                            axes[0, 1].set_title("线扩散函数 (LSF)", fontsize=12)
                            axes[0, 1].set_xlim(0, None)
                            axes[0, 1].grid(True)
                        else:
                            axes[0, 1].text(
                                0.5,
                                0.5,
                                "无LSF数据",
                                ha="center",
                                va="center",
                                transform=axes[0, 1].transAxes,
                            )
                            axes[0, 1].set_title("线扩散函数 (LSF)", fontsize=12)

                        # 3. 绘制SFR（空间频率响应）- 左下
                        colors = ["red", "green", "blue", "black"]
                        num_channels = dat.shape[1] - 1

                        # 判断是否为单色图像（只有1个通道）
                        is_monochrome = num_channels == 1

                        # 通道名称映射
                        channel_names = ["R", "G", "B", "Lum"]

                        for i in range(num_channels):
                            # 使用通道名称而不是通道编号
                            # 对于单色图像，显示为Lum通道
                            if is_monochrome:
                                channel_name = "Lum"
                            else:
                                channel_name = (
                                    channel_names[i]
                                    if i < len(channel_names)
                                    else f"通道{i}"
                                )
                            axes[1, 0].plot(
                                dat[:, 0],
                                dat[:, i + 1],
                                color=colors[i % len(colors)],
                                label=channel_name
                                if not is_monochrome
                                else "",  # 单色时不显示图例
                            )

                        # 对于彩色图像，只绘制不带marker的Lum通道（避免重复）
                        if num_channels > 1:
                            # 检查是否已经有Lum通道的曲线
                            has_lum_curve = False
                            for i in range(num_channels):
                                if i < len(channel_names) and channel_names[i] == "Lum":
                                    has_lum_curve = True
                                    break

                            # 如果没有Lum通道的曲线，则绘制散点
                            if not has_lum_curve:
                                axes[1, 0].scatter(
                                    dat[:, 0],
                                    dat[:, -1],
                                    s=40,
                                    marker="o",
                                    facecolors="none",
                                    edgecolors="black",
                                    label="Lum"
                                    if not is_monochrome
                                    else "",  # 单色时不显示图例
                                )

                        # 设置x轴标签
                        if is_dpi:
                            axes[1, 0].set_xlabel("频率(cycles/pixel)", fontsize=10)
                        else:
                            axes[1, 0].set_xlabel("频率(cycles/mm)", fontsize=10)

                        axes[1, 0].set_xlim(0, None)
                        axes[1, 0].set_ylim(0, 1)
                        axes[1, 0].set_ylabel("SFR", fontsize=10)
                        axes[1, 0].set_title("空间频率响应", fontsize=12)

                        # 添加采样效率数据
                        if e is not None and e.shape[1] > 0:
                            channel_names = ["R", "G", "B", "Lum"]
                            text_str = "采样效率:\n"
                            # 对于单色图像，显示为Lum通道的采样效率
                            if e.shape[1] == 1:
                                text_str += f"Lum: {e[0, 0]:.1f}%\n"
                            else:
                                for i in range(min(e.shape[1], len(channel_names))):
                                    text_str += f"{channel_names[i]}: {e[0, i]:.1f}%\n"

                            axes[1, 0].text(
                                0.98,
                                0.98,
                                text_str,
                                transform=axes[1, 0].transAxes,
                                horizontalalignment="right",
                                verticalalignment="top",
                                bbox=dict(
                                    boxstyle="round", facecolor="white", alpha=0.8
                                ),
                            )

                        axes[1, 0].legend()
                        axes[1, 0].grid(True)

                        # 4. 显示ROI图像 - 右下
                        if self.calculator.image is not None:
                            # 归一化图像数据到[0, 1]范围用于显示
                            display_image = self.calculator.image.copy()
                            if len(display_image.shape) == 3:
                                # RGB图像
                                if display_image.max() > 1:
                                    display_image = display_image / 255.0
                                axes[1, 1].imshow(display_image)
                            else:
                                # 灰度图像
                                if display_image.max() > 1:
                                    display_image = display_image / 255.0
                                axes[1, 1].imshow(display_image, cmap="gray")

                            axes[1, 1].set_title("ROI图像", fontsize=12)
                            axes[1, 1].axis("off")
                        else:
                            axes[1, 1].text(
                                0.5,
                                0.5,
                                "无图像数据",
                                ha="center",
                                va="center",
                                transform=axes[1, 1].transAxes,
                            )
                            axes[1, 1].set_title("ROI图像", fontsize=12)

                        plt.tight_layout()
                        plt.show()

                        window["-STATUSBAR-"].update("多图表已显示")
                    else:
                        self.sg.popup_error("无有效结果可显示")

                except Exception as e:
                    self.sg.popup_error(f"无法显示多图: {str(e)}")

            elif event == "-SAVE_DATA-":
                if self.results is None:
                    self.sg.popup_error("无数据可保存")
                    continue

                # 保存数据到Excel文件
                try:
                    import pandas as pd

                    status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = self.results

                    if status == 0 and dat is not None:
                        # 获取保存路径
                        save_path = self.sg.popup_get_file(
                            "保存数据",
                            save_as=True,
                            default_extension=".xlsx",
                            file_types=(
                                ("Excel文件", "*.xlsx"),
                                ("所有文件", "*.*"),
                            ),
                            no_window=True,
                            keep_on_top=True,
                        )

                        if save_path:
                            if not save_path.endswith(".xlsx"):
                                save_path += ".xlsx"

                            # 创建DataFrame用于保存SFR数据
                            columns = ["频率"]
                            channel_names = ["R", "G", "B", "Lum"]
                            # 对于单色图像，显示为Lum通道
                            if dat.shape[1] - 1 == 1:
                                columns.append("Lum")
                            else:
                                for i in range(dat.shape[1] - 1):
                                    if i < len(channel_names):
                                        columns.append(channel_names[i])
                                    else:
                                        columns.append(f"通道{i}")

                            sfr_df = pd.DataFrame(dat, columns=columns)

                            # 创建Excel写入器
                            with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                                # 创建基本信息工作表 - 第一个工作表
                                info_data = {
                                    "参数": [
                                        "状态",
                                        "合并因子",
                                        "采样间隔",
                                        "频率单位",
                                        "SFR50",
                                    ],
                                    "数值": [
                                        "成功" if status == 0 else "失败",
                                        nbin,
                                        f"{del2:.4f}",
                                        "cycles/pixel" if is_dpi else "cycles/mm",
                                        f"{sfr50:.4f}",
                                    ],
                                }
                                info_df = pd.DataFrame(info_data)
                                info_df.to_excel(
                                    writer, sheet_name="基本信息", index=False
                                )

                                # 写入SFR数据到第二个工作表
                                sfr_df.to_excel(
                                    writer, sheet_name="SFR数据", index=False
                                )

                                # 创建采样效率工作表 - 第三个工作表
                                if e is not None and e.shape[1] > 0:
                                    efficiency_data = {"通道": [], "采样效率(%)": []}
                                    # 对于单色图像，显示为Lum通道的采样效率
                                    if e.shape[1] == 1:
                                        efficiency_data["通道"].append("Lum")
                                        efficiency_data["采样效率(%)"].append(
                                            f"{e[0, 0]:.1f}"
                                        )
                                    else:
                                        for i in range(
                                            min(e.shape[1], len(channel_names))
                                        ):
                                            efficiency_data["通道"].append(
                                                channel_names[i]
                                            )
                                            efficiency_data["采样效率(%)"].append(
                                                f"{e[0, i]:.1f}"
                                            )

                                    efficiency_df = pd.DataFrame(efficiency_data)
                                    efficiency_df.to_excel(
                                        writer, sheet_name="采样效率", index=False
                                    )

                            self.sg.popup("成功", f"数据已保存到 {save_path}")
                            window["-STATUSBAR-"].update("数据已保存")
                    else:
                        self.sg.popup_error("无有效数据可保存")

                except ImportError:
                    self.sg.popup_error("未安装pandas库，无法保存Excel文件")
                    print("请运行: pip install pandas openpyxl")
                except Exception as e:
                    self.sg.popup_error(f"保存数据失败: {str(e)}")

        # 关闭窗口
        window.close()


def main():
    """主函数"""
    logger.info("启动SFRMAT5 GUI")
    gui = SFRMatGUI()
    gui.run()


if __name__ == "__main__":
    main()

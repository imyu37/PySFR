"""
SFRMAT5 GUI界面
基于MATLAB sfrmat5.m的Python实现
"""

import io
import logging
import os
import tkinter as tk
from tkinter import filedialog

import cv2
import FreeSimpleGUI as sg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import RectangleSelector
from PIL import Image
from scipy import fft, signal

from sfrmat5 import SFRCalculator

# 配置matplotlib中文显示
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
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
        fig, ax = plt.subplots(1, 1, figsize=(10, 8))

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
                facecolor="none",
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

    def create_layout(self):
        """创建GUI布局"""

        # 标题栏
        title_layout = [
            [
                sg.Text(
                    "SFRMAT5 - 空间频率响应分析",
                    font=("微软雅黑", 16, "bold"),
                    justification="center",
                    expand_x=True,
                )
            ],
        ]

        # 图像控制区域
        image_control_layout = [
            [sg.Text("图像选择", font=("微软雅黑", 11, "bold"))],
            [
                sg.Button("加载图像", size=(12, 1), key="-LOAD_IMAGE-"),
                sg.Button("选择ROI", size=(12, 1), key="-CHOOSE_ROI-"),
                sg.Button("清除ROI", size=(12, 1), key="-CLEAR_ROI-"),
            ],
            [sg.Text("状态: 未加载图像", key="-STATUS-", size=(50, 1))],
        ]

        # 参数设置区域
        params_layout = [
            [sg.Text("分析参数", font=("微软雅黑", 11, "bold"))],
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
            [sg.Text("图像预览", font=("微软雅黑", 11, "bold"))],
            [
                sg.Image(
                    key="-IMAGE_PREVIEW-", size=(400, 420), background_color="lightgray"
                )
            ],
            [sg.Text("ROI坐标:", key="-ROI_COORDS-", size=(50, 1))],
        ]

        # 分析控制区域
        analysis_layout = [
            [sg.Text("分析控制", font=("微软雅黑", 11, "bold"))],
            [
                sg.Button(
                    "计算SFR",
                    size=(14, 2),
                    key="-CALCULATE_SFR-",
                    button_color=("white", "green"),
                ),
                sg.Button("显示图表", size=(14, 2), key="-SHOW_PLOTS-"),
                sg.Button("导出结果", size=(14, 2), key="-EXPORT_RESULTS-"),
            ],
        ]

        # 结果区域
        results_layout = [
            [sg.Text("分析结果", font=("微软雅黑", 11, "bold"))],
            [
                sg.Multiline(
                    size=(80, 8),
                    key="-RESULTS_TEXT-",
                    disabled=True,
                    autoscroll=True,
                    font=("Courier", 9),
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

        # 使用tkinter文件对话框
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口

        file_path = filedialog.askopenfilename(
            title="选择图像文件",
            filetypes=(
                ("图像文件", "*.png *.jpg *.jpeg *.tiff *.tif *.bmp *.gif"),
                ("所有文件", "*.*"),
            ),
        )
        root.destroy()

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
                # 裁剪图像到ROI
                cropped_image = crop_to_roi(self.calculator.image, self.roi_coords)

                # 更新预览
                display_image = cropped_image.copy()
                if len(display_image.shape) == 3:
                    display_image = (display_image / display_image.max() * 255).astype(
                        np.uint8
                    )
                else:
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

    def display_results(self, window, results):
        """在结果区域显示分析结果"""
        status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = results

        if status != 0 or dat is None:
            result_str = "SFR计算失败"
        else:
            # 构建结果字符串
            result_str = f"""SFR分析结果
{"=" * 50}

基本参数:
- 状态: {"成功" if status == 0 else "失败"}
- 合并因子: {nbin}
- 采样间隔: {del2:.4f}
- 频率单位: {"cycle/mm" if is_dpi else "cycle/pixel"}

关键指标:
- SFR50: {sfr50:.4f}

采样效率:
"""

            # 添加各通道的采样效率
            channel_names = ["R", "G", "B", "Lum"]
            if e is not None and e.shape[1] > 0:
                for i in range(min(e.shape[1], len(channel_names))):
                    result_str += f"- {channel_names[i]}: {e[0, i]:.1f}%\n"

        window["-RESULTS_TEXT-"].update(result_str)
        self.results = results

    def run(self):
        """启动GUI事件循环"""
        # 创建窗口
        layout = self.create_layout()
        window = sg.Window("SFRMAT5", layout, size=(850, 600), resizable=True)

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

                        plt.figure(figsize=(10, 6))

                        for i in range(num_channels):
                            plt.plot(
                                dat[:, 0],
                                dat[:, i + 1],
                                color=colors[i % len(colors)],
                                label=f"通道{i}",
                            )

                        # 亮度通道使用散点绘制
                        plt.scatter(
                            dat[:, 0],
                            dat[:, -1],
                            s=40,
                            marker="o",
                            facecolors="none",
                            edgecolors="black",
                            label="Lum",
                        )

                        # 设置x轴标签
                        if is_dpi:
                            plt.xlabel("频率(cycle/mm)")
                        else:
                            plt.xlabel("频率(cycle/pixel)")

                        plt.xlim(0, None)
                        plt.ylim(0, 1)
                        plt.ylabel("SFR")
                        plt.title("空间频率响应")

                        # 添加采样效率数据
                        if e is not None and e.shape[1] > 0:
                            channel_names = ["R", "G", "B", "Lum"]
                            text_str = "采样效率:\n"
                            for i in range(min(e.shape[1], len(channel_names))):
                                text_str += f"{channel_names[i]}: {e[0, i]:.1f}%\n"

                            plt.text(
                                0.98,
                                0.98,
                                text_str,
                                transform=plt.gca().transAxes,
                                horizontalalignment="right",
                                verticalalignment="top",
                                bbox=dict(
                                    boxstyle="round", facecolor="white", alpha=0.8
                                ),
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

            elif event == "-EXPORT_RESULTS-":
                if self.results is None:
                    self.sg.popup_error("无结果可导出")
                    continue

                # 导出结果到Excel文件
                try:
                    import pandas as pd

                    status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = self.results

                    if status == 0 and dat is not None:
                        # 创建DataFrame
                        columns = ["频率"]
                        channel_names = ["R", "G", "B", "Lum"]
                        for i in range(dat.shape[1] - 1):
                            if i < len(channel_names):
                                columns.append(channel_names[i])
                            else:
                                columns.append(f"通道{i}")

                        df = pd.DataFrame(dat, columns=columns)

                        # 保存到Excel文件
                        export_path = self.sg.popup_get_file(
                            "保存结果",
                            save_as=True,
                            default_extension=".xlsx",
                            file_types=(("Excel文件", "*.xlsx"),),
                        )

                        if export_path:
                            if not export_path.endswith(".xlsx"):
                                export_path += ".xlsx"

                            df.to_excel(export_path, index=False)
                            self.sg.popup("成功", f"结果已导出到 {export_path}")
                            window["-STATUSBAR-"].update("结果已导出")
                    else:
                        self.sg.popup_error("无有效结果可导出")

                except ImportError:
                    self.sg.popup_error("未安装pandas库，无法导出Excel文件")
                    print("请运行: pip install pandas openpyxl")
                except Exception as e:
                    self.sg.popup_error(f"导出失败: {str(e)}")

        # 关闭窗口
        window.close()


def main():
    """主函数"""
    logger.info("启动SFRMAT5 GUI")
    gui = SFRMatGUI()
    gui.run()


if __name__ == "__main__":
    main()

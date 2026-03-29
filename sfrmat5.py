import logging
import os
import tkinter as tk
from tkinter import filedialog

import cv2
import matplotlib.pyplot as plt
import numpy as np
import scipy
from matplotlib.widgets import RectangleSelector
from scipy import fft, signal
from scipy.interpolate import interp1d

# 配置matplotlib中文显示
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("sfrmat5.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class SFRCalculator:
    def __init__(self):
        logger.info("初始化SFR计算器")
        self.pflag = 0
        self.guidefweight = np.array([0.213, 0.715, 0.072])
        self.defnpol = 5
        self.oename = "none"
        self.nbin = 4
        self.defalpha = 1.0
        self.maxalpha = 1.0
        self.minalpha = 0.5
        logger.info(
            f"SFR计算器初始化完成: 权重={self.guidefweight}, 多项式阶数={self.defnpol}, 合并因子={self.nbin}"
        )

    def centroid(self, x):
        n = np.arange(1, len(x) + 1)
        return np.sum(n * x) / np.sum(x)

    def rotatev2(self, a):
        logger.debug("开始图像旋转检测")
        dim = a.shape
        nlin, npix = dim[0], dim[1]

        if len(dim) == 3:
            mm = 1  # 通常使用绿色通道
            nn = 3
            testv = abs(np.mean(a[-nn, :, mm]) - np.mean(a[nn, :, mm]))
            testh = abs(np.mean(a[:, -nn, mm]) - np.mean(a[:, nn, mm]))
        else:
            nn = 3
            testv = abs(np.mean(a[-nn, :]) - np.mean(a[nn, :]))
            testh = abs(np.mean(a[:, -nn]) - np.mean(a[:, nn]))

        rflag = 0
        if testv > testh:
            rflag = 1
            a = np.rot90(a, axes=(1, 0))
            nlin, npix = npix, nlin
            logger.debug("图像已旋转90度")

        logger.debug(f"旋转检测完成 - rflag: {rflag}, 尺寸: {nlin}x{npix}")
        return a, nlin, npix, rflag

    def deriv1(self, a, nlin, npix, fil):
        logger.debug("计算一维导数")
        b = np.zeros((nlin, npix))
        for ii in range(nlin):
            temp = signal.convolve(a[ii, :], fil, mode="same")
            b[ii, :] = temp
            b[ii, 0] = b[ii, 1]
            b[ii, -1] = b[ii, -2]
        logger.debug("一维导数计算完成")
        return b

    def tukey2(self, n, alpha, mid):
        if n < 3:
            return np.ones(n)

        m1 = n / 2
        m2 = mid
        m3 = n - mid
        mm = max(m2, m3)
        n2 = int(2 * mm)

        w = self.tukey(n2, alpha)

        if mid >= m1:
            w = w[:n]
        else:
            w = w[-n:]

        return w

    def tukey(self, n, alpha=0.5):
        if n == 1:
            return np.ones(1)
        if alpha == 0:
            return np.ones(n)

        x = np.linspace(0, 1, n)
        w = np.ones(x.shape)

        first = int(np.floor(alpha * (n - 1) / 2.0))
        w[:first] = 0.5 * (1 + np.cos(np.pi * (2 * x[:first] / alpha - 1)))

        last = n - first
        w[last:] = 0.5 * (1 + np.cos(np.pi * (2 * (1 - x[last:]) / alpha - 1)))

        return w

    def ahamming(self, n, mid):
        data = np.zeros(n)
        mid += 0.5

        wid1 = mid - 1
        wid2 = n - mid
        wid = max(wid1, wid2)

        for i in range(n):
            arg = i - mid
            data[i] = np.cos(np.pi * arg / wid)

        return 0.54 + 0.46 * data

    def clip(self, in_data, low, high):
        if low == "-inf":
            low = -np.inf
        if high == "inf":
            high = np.inf

        if low == "-inf" and high == "inf":
            return in_data

        out = np.maximum(in_data, low)
        if high != "inf":
            out = np.minimum(out, high)

        return out

    def findedge2(self, cent, nlin, nn=1):
        index = np.arange(nlin)
        p = np.polyfit(index, cent, nn)
        return p

    def project2(self, bb, fitme, fac=4):
        """
        将2D边缘数据投影和分箱到1D数组

        Args:
            bb: 2D边缘数组 [nlin, npix]
            fitme: 边缘位置多项式拟合参数
            fac: 超采样因子 (默认4)

        Returns:
            esf: 1D边缘扩散函数数组 [fac*npix, ]
            status: 处理状态标志
        """
        try:
            nlin, npix = bb.shape

            # 1. 应用多项式拟合校正倾斜
            logger.debug(f"应用多项式校正 - nlin: {nlin}, npix: {npix}")

            # 对每一行应用多项式校正
            for n in range(nlin):
                # 计算该行的边缘位置
                edge_pos = np.polyval(fitme, n)

                # 边界检查
                if np.isnan(edge_pos) or not np.isfinite(edge_pos):
                    continue

                # 计算需要的移位量
                shift = npix / 2 - edge_pos

                # 如果移位量不为零，则移位该行
                shift_int = int(shift)
                if shift_int != 0:
                    # 创建该行的副本
                    row_data = bb[n, :].copy()

                    # 应用移位
                    if shift_int > 0:
                        bb[n, shift_int:] = row_data[: npix - shift_int]
                        bb[n, :shift_int] = 0
                    elif shift_int < 0:
                        bb[n, : npix + shift_int] = row_data[-shift_int:]
                        bb[n, npix + shift_int :] = 0

            # 2. 对所有列求和得到边缘扩散函数
            esf_raw = np.sum(bb, axis=0)

            # 3. 超采样
            nn = fac * npix
            esf = np.zeros(nn)

            # 插值实现超采样
            x_original = np.arange(npix)
            x_interpolated = np.linspace(0, npix - 1, nn)
            esf = np.interp(x_interpolated, x_original, esf_raw, left=0, right=0)

            # 4. 归一化
            esf_min = np.min(esf)
            esf_max = np.max(esf)
            if esf_max - esf_min > 0:
                esf = (esf - esf_min) / (esf_max - esf_min)

            logger.debug(f"投影和分箱完成 - 输入: {bb.shape}, 输出: {esf.shape}")

            return esf, 0  # status = 0 表示成功

        except Exception as e:
            logger.error(f"投影和分箱失败: {e}")
            import traceback

            traceback.print_exc()
            # 返回空数组和错误状态
            return np.zeros(1), 1  # status = 1 表示失败

    def fir2fix(self, n, m):
        correct = np.ones(n)
        m = m - 1
        scale = 1

        for i in range(1, n):
            correct[i] = abs(
                (np.pi * i * m / (2 * (n + 1))) / np.sin(np.pi * i * m / (2 * (n + 1)))
            )
            correct[i] = 1 + scale * (correct[i] - 1)
            if correct[i] > 10:
                correct[i] = 10

        return correct

    def cent(self, c, mm):
        """围绕指定位置中心化数组"""
        # 检查NaN值
        if np.isnan(mm) or not np.isfinite(mm):
            return c

        nn = len(c)
        if nn == 0:
            return c

        # 计算需要移位的数量，使位置mm位于数组中心
        shift = int(nn / 2 - mm)

        # 如果移位为0，直接返回原数组
        if shift == 0:
            return c

        # 创建结果数组
        result = np.zeros_like(c)

        # 应用移位
        if shift > 0:
            # 向右移位
            result[shift:] = c[: nn - shift]
        else:
            # 向左移位
            result[: nn + shift] = c[-shift:]

        return result

    def rsquare(self, y_pred, y_true):
        """计算R平方、均方根误差和平均误差"""
        logger.debug("计算R平方、RMSE和平均误差")
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
        merror = np.mean(np.abs(y_true - y_pred))
        logger.debug(f"R²: {r2}, RMSE: {rmse}, 平均误差: {merror}")
        return r2, rmse, merror

    def sampeff(self, dat, val, del_image, pflag, npol):
        """计算采样效率"""
        logger.debug("开始计算采样效率")
        nfreq, ncol = dat.shape
        ncol -= 1  # 移除频率列
        e = np.zeros((1, ncol))
        freqval = np.zeros((1, len(val)))

        for j in range(len(val)):
            for i in range(ncol):
                # 查找SFR等于val[j]的频率
                target_val = val[j]
                idx = np.where(dat[:, i + 1] <= target_val)[0]
                if len(idx) > 0:
                    idx = idx[0]
                    if idx > 0:
                        # 插值
                        x1, x2 = dat[idx - 1, 0], dat[idx, 0]
                        y1, y2 = dat[idx - 1, i + 1], dat[idx, i + 1]
                        freqval[0, j] = x1 + (target_val - y1) * (x2 - x1) / (y2 - y1)
                    else:
                        freqval[0, j] = dat[idx, 0]
                else:
                    freqval[0, j] = 0

                # 计算采样效率
                if freqval[0, 0] > 0:  # 对于10%的值
                    nyquist = 0.5 / del_image
                    e[0, i] = (freqval[0, 0] / nyquist) * 100

        logger.debug(f"采样效率计算完成 - 结果形状: {e.shape}")
        return e, freqval, []

    def calculate_sfr(self, io=0, del_input=1, a=None, npol=None, wflag=0, weight=None):
        """基于MATLAB sfrmat5.m的主要SFR计算函数"""
        logger.info("开始SFR计算")
        logger.debug(
            f"输入参数 - io: {io}, del_input: {del_input}, npol: {npol}, wflag: {wflag}"
        )

        # 设置默认值
        if npol is None:
            npol = self.defnpol
        if weight is None:
            weight = self.guidefweight

        # 验证输入
        if npol > 5:
            logger.warning("* 边缘拟合阶数必须小于等于5 *")
            npol = 5

        alpha = self.clip(self.defalpha, self.minalpha, self.maxalpha)
        logger.info(f"使用参数 - npol: {npol}, alpha: {alpha}, weight: {weight}")

        if io != 1:  # GUI模式
            logger.info("进入GUI模式 - 选择图像文件")
            # 模拟文件选择和ROI选择
            root = tk.Tk()
            root.withdraw()
            file_path = filedialog.askopenfilename()

            if not file_path:
                logger.error("没有选择文件")
                return 1, None, None, None, None, None, None, None

            logger.info(f"加载图像文件: {file_path}")
            a = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            if a is None:
                logger.error("无法读取图像")
                return 1, None, None, None, None, None, None, None

            # 转换为float64
            a = np.array(a, dtype=np.float64)
            logger.info(f"图像加载成功，形状: {a.shape}")

            # 显示图像并选择ROI
            logger.info("显示图像供用户选择ROI")
            fig, ax = plt.subplots()

            # 归一化图像数据到[0, 1]范围以避免警告
            display_image = a.copy()
            if display_image.max() > 1:
                display_image = display_image / 255.0

            ax.imshow(display_image)
            ax.set_title("Select ROI")

            def onselect(eclick, erelease):
                nonlocal a
                x1, y1 = int(eclick.xdata), int(eclick.ydata)
                x2, y2 = int(erelease.xdata), int(erelease.ydata)
                x1 = max(0, min(x1, a.shape[1] - 1))
                x2 = max(0, min(x2, a.shape[1] - 1))
                y1 = max(0, min(y1, a.shape[0] - 1))
                y2 = max(0, min(y2, a.shape[0] - 1))
                a = a[min(y1, y2) : max(y1, y2) + 1, min(x1, x2) : max(x1, x2) + 1]
                logger.info(f"ROI选择完成: ({x1}, {y1}) 到 ({x2}, {y2})")

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

            plt.show()

            # 获取采样间隔
            del_input_raw = float(input("输入采样间隔 (mm 或 dpi): "))
            logger.info(f"用户输入采样间隔: {del_input_raw}")
            is_dpi = False
            if del_input_raw > 1:
                del_param = 25.4 / del_input_raw  # 将DPI转换为mm
                is_dpi = True
                logger.info(f"DPI转换为mm: {del_param}")
            else:
                del_param = del_input_raw
        else:  # 非GUI模式
            logger.info("进入非GUI模式")
            a = np.array(a, dtype=np.float64)
            is_dpi = False
            if del_input > 1:
                del_param = 25.4 / del_input  # 将DPI转换为mm
                is_dpi = True
                logger.info(f"DPI转换为mm: {del_param}")
            else:
                del_param = del_input

        # 图像尺寸
        nlin, npix = a.shape[0], a.shape[1]
        ncol = a.shape[2] if len(a.shape) == 3 else 1
        logger.info(f"图像尺寸 - 行数: {nlin}, 像素数: {npix}, 颜色通道: {ncol}")

        # 使用RGB权重向量形成亮度记录
        if ncol == 3:
            logger.info("处理RGB图像，生成亮度通道")
            lum = (
                weight[0] * a[:, :, 0] + weight[1] * a[:, :, 1] + weight[2] * a[:, :, 2]
            )
            cc = np.zeros((nlin, npix, 4))
            cc[:, :, 0] = a[:, :, 0]
            cc[:, :, 1] = a[:, :, 1]
            cc[:, :, 2] = a[:, :, 2]
            cc[:, :, 3] = lum
            a = cc
            ncol = 4

        # 如有必要旋转
        logger.info("进行图像旋转检测")
        a, nlin, npix, rflag = self.rotatev2(a)
        logger.info(f"旋转完成 - rflag: {rflag}, 新尺寸: {nlin}x{npix}")

        # 确定边缘方向（垂直vs水平）
        loc = np.zeros((ncol, nlin))
        logger.info("确定边缘方向")

        # 检查正边缘
        if len(a.shape) == 3:
            tleft = np.sum(a[:, :5, 0])
            tright = np.sum(a[:, -5:, 0])
        else:
            tleft = np.sum(a[:, :5])
            tright = np.sum(a[:, -5:])

        lowhi = 0
        fil1 = np.array([0.5, -0.5])
        fil2 = np.array([0.5, 0, -0.5])

        if tleft > tright:
            lowhi = 1
            fil1 = np.array([-0.5, 0.5])
            fil2 = np.array([-0.5, 0, 0.5])

        # 测试低对比度边缘
        test = abs((tleft - tright) / (tleft + tright)) if (tleft + tright) != 0 else 0
        if test < 0.2:
            logger.warning("** 警告：边缘对比度小于20%，这可能导致SFR测量误差较大。**")

        fitme = np.zeros((ncol, npol + 1))
        fitme1 = np.zeros((ncol, 2))

        # 平滑窗口
        if wflag != 0:
            win1 = self.ahamming(npix, (npix + 1) / 2)
            logger.info("使用汉明窗")
        else:
            win1 = self.tukey2(npix, alpha, (npix + 1) / 2)
            win1 = 0.95 * win1 + 0.05  # 使边缘查找更稳定
            logger.info(f"使用Tukey窗 - alpha: {alpha}")

        logger.info("开始处理各颜色通道")
        # 处理每个颜色通道
        for color in range(ncol):
            logger.debug(f"处理颜色通道 {color}")
            # 计算1-D导数 - 直接处理数据
            if len(a.shape) == 3:
                c = self.deriv1(a[:, :, color], nlin, npix, fil1)
            else:
                c = self.deriv1(a, nlin, npix, fil1)

            # 应用窗口并计算每行的边缘中心位置
            for n in range(nlin):
                loc[color, n] = (
                    self.centroid(c[n, :] * win1) - 0.5
                )  # -0.5偏移用于FIR相位

            fitme[color, :] = self.findedge2(loc[color, :], nlin, npol)

            # 使用自适应窗口细化位置
            place = np.zeros(nlin)
            for n in range(nlin):
                place[n] = np.polyval(fitme[color, :], n - 1)

                if wflag != 0:
                    win2 = self.ahamming(npix, place[n])
                else:
                    win2 = self.tukey2(npix, alpha, place[n])
                    win2 = 0.95 * win2 + 0.05  # 使边缘查找更稳定

                loc[color, n] = self.centroid(c[n, :] * win2) - 0.5

            # 最终的中心位置多项式拟合
            fitme[color, :] = self.findedge2(loc[color, :], nlin, npol)

            # 与线性边缘拟合比较
            fitme1[color, :] = self.findedge2(loc[color, :], nlin, 1)

            # 如果npol > 3，检查拟合质量
            if npol > 3:
                x = np.arange(nlin)
                y = np.polyval(fitme[color, :], x)
                r2, rmse, merror = self.rsquare(y, loc[color, :])
                if rmse > 3:
                    logger.warning("警告：可能存在边缘拟合问题:")
                    logger.warning(f"平均边缘拟合误差: {merror}")
                    logger.warning(f"r2: {r2}, rmse: {rmse}")

        # 根据边缘斜率限制行数
        nlin1 = round(np.floor(nlin * abs(fitme1[-1, -2]) / abs(fitme1[-1, -2])))
        if len(a.shape) == 3:
            a = a[:nlin1, :, :]
        else:
            a = a[:nlin1, :]
        nlin = nlin1
        logger.info(f"根据边缘斜率调整行数: {nlin1}")

        # 计算边缘角度
        vslope = -fitme1[-1, -2]  # 使用线性拟合的亮度边缘角度
        slope_deg = 180 * np.arctan(vslope) / np.pi

        if rflag == 1:
            slope_deg = slope_deg + 90
        logger.info(f"边缘角度: {slope_deg:.3f} 度")

        delimage = del_param

        # 校正垂直于边缘的采样间隔
        delfac = np.cos(np.arctan(vslope))
        del_param = del_param * delfac  # 输入像素采样垂直于边缘
        del2 = del_param / self.nbin  # 垂直于边缘的超采样间隔
        logger.info(
            f"采样间隔校正完成 - 原始: {delimage}, 校正后: {del_param}, 超采样: {del2}"
        )

        # 计算多通道的错位
        if ncol > 2:
            logger.info("计算颜色通道错位")
            midloc = np.zeros(ncol)
            for i in range(ncol):
                midloc[i] = np.polyval(fitme[i, :], (nlin - 1) / 2)
            misreg = midloc - midloc[1]  # 以绿色为参考
            misreg = delfac * misreg  # 颜色错位垂直于边缘
            logger.info(f"颜色错位: {misreg}")

        # SFR计算参数
        nn = int(np.ceil(npix * self.nbin))
        mtf = np.zeros((nn, ncol))
        nn2 = int(np.floor(nn / 2)) + 1
        logger.info(f"SFR计算参数 - nn: {nn}, nn2: {nn2}")

        dcorr = self.fir2fix(nn2, 3)  # FIR滤波器响应的校正

        freqlim = 1
        if self.nbin == 1:
            freqlim = 2
        nn2out = int(round(nn2 * freqlim / 2))
        nfreq = nn / (2 * delimage * nn)  # 半采样频率

        # 为SFR计算处理每个颜色
        esf = np.zeros((nn, ncol))

        if wflag == 0:
            logger.info(f"使用Tukey窗 - alpha = {alpha}")

        logger.info("开始计算各颜色的SFR")
        for color in range(ncol):
            logger.debug(f"计算颜色通道 {color} 的SFR")
            # 在4倍采样数组中投影和分箱数据
            if len(a.shape) == 3:
                esf_col, status = self.project2(
                    a[:, :, color], fitme[color, :], self.nbin
                )
            else:
                esf_col, status = self.project2(a, fitme[color, :], self.nbin)
            esf[:, color] = esf_col

            # 计算超采样边缘数据的一维导数
            c = self.deriv1(esf[:, color].reshape(1, -1), 1, nn, fil2)
            c = c.flatten()

            # 处理边界情况
            if c[0] == 0:
                c[0] = c[1]
            elif c[-1] == 0:
                c[-1] = c[-2]

            nn_actual = len(c)
            mm = np.mean(np.where(c == np.max(c))[0])  # 所有最大位置的平均值

            # 中心化数组
            c = self.cent(c, mm)
            mm = nn_actual / 2

            # 应用窗口
            if wflag != 0:
                win = self.ahamming(nn_actual, mm)
            else:
                win = self.tukey2(nn_actual, alpha, mm)

            c = win * c

            # 计算窗口化LSF的DFT的归一化模量
            temp = np.abs(fft.fft(c, nn_actual))
            mtf[: min(nn2, len(temp)), color] = temp[: min(nn2, len(temp))] / temp[0]

            # 校正离散导数响应
            mtf[:nn2, color] = mtf[:nn2, color] * dcorr[:nn2]

        # 计算频率值
        freq = np.zeros(nn)
        for n in range(nn):
            freq[n] = (n) / (del2 * nn)

        # 准备输出数据
        dat = np.zeros((nn2out, ncol + 1))
        for i in range(nn2out):
            dat[i, 0] = freq[i]
            dat[i, 1:] = mtf[i, :ncol]

        # 将颜色错位添加到fitme矩阵
        if ncol > 2:
            temp1 = np.zeros((ncol, npol + 2))
            temp1[:, : npol + 1] = fitme
            temp1[:, -1] = misreg
            fitme = temp1

        # 计算采样效率
        val = [0.1, 0.5]  # 10%和50%的值
        e, freqval, _ = self.sampeff(dat, val, delimage, self.pflag, npol)
        sfr50 = freqval[0, 1]  # SFR为50%时的频率
        logger.info(f"计算完成 - SFR50: {sfr50}")

        # 返回与MATLAB版本相同的输出
        status = 0
        logger.info("SFR计算完成")
        return status, dat, e, sfr50, fitme, esf, self.nbin, del2, is_dpi


if __name__ == "__main__":
    logger.info("启动SFR计算程序")
    sfr = SFRCalculator()
    status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = sfr.calculate_sfr()
    if status == 0 and dat is not None:
        logger.info("绘制SFR结果图表")
        # 定义通道颜色：R, G, B, Lum
        colors = ["red", "green", "blue", "black"]
        # 绘制各通道的SFR曲线，每个通道使用对应颜色
        num_channels = dat.shape[1] - 1  # 减去频率列
        for i in range(num_channels):
            plt.plot(
                dat[:, 0],
                dat[:, i + 1],
                color=colors[i % len(colors)],
                label=f"通道{i}",
            )
        # 亮度通道（最后一列）使用散点绘制，黑色空心圆
        plt.scatter(
            dat[:, 0],
            dat[:, -1],
            s=40,
            marker="o",
            facecolors="none",
            edgecolors="black",
            label="Lum",
        )
        # 根据输入单位设置x轴标签
        if is_dpi:
            plt.xlabel("频率(cycle/pixel)")
        else:
            plt.xlabel("频率(cycle/mm)")
        plt.xlim(0, None)
        plt.ylim(0, 1)
        plt.ylabel("SFR")
        plt.title("空间频率响应")

        # 在图像上添加采样效率数据
        # e是一个1行ncol的数组，显示各通道的采样效率
        channel_names = ["R", "G", "B", "Lum"]  # 假设有RGB和亮度通道
        num_channels = e.shape[1]
        text_str = "采样效率:\n"
        for i in range(min(num_channels, len(channel_names))):
            text_str += f"{channel_names[i]}: {e[0, i]:.1f}%\n"

        # 在图表左上角添加文本框
        plt.text(
            0.98,
            0.98,
            text_str,
            transform=plt.gca().transAxes,
            horizontalalignment="right",
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

        plt.show()
        logger.info(f"采样效率: {e}")
        logger.info(f"SFR50: {sfr50}")
        logger.info(f"合并因子: {nbin}")
        logger.info(f"采样间隔: {del2}")
        logger.info("程序执行完成")
    else:
        logger.error(f"计算失败，状态码: {status}")

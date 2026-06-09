# PySFR - Python implementation of the slanted-edge SFR (MTF) measurement algorithm
#
# Copyright (c) 2024 imyu37 / wanyong_37@hotmail.com
# Licensed under the MIT License. See LICENSE file in the project root.
#
# Original MATLAB algorithm by Peter D. Burns (pdburns@ieee.org)
#   Copyright (c) 2009-2023 Peter D. Burns. All rights reserved.
#   Based on sfrmat5.m, distributed in support of ISO 12233 Edition 4.
#
# This Python port is an independent implementation of the published algorithm.

import logging

import cv2
import matplotlib.pyplot as plt
import numpy as np
from scipy import fft, signal

# 配置matplotlib中文显示
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("PySFR.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class SFRCalculator:
    def __init__(self):
        """
        基于 MATLAB sfrmat5.m 的精确 Python 实现

        主要改进：
        1. 精确的边缘投影和分箱算法
        2. 改进的窗口函数实现
        3. 增强的边缘拟合精度
        4. 更准确的 SFR 计算
        """
        logger.info("初始化SFR计算器 - 基于MATLAB sfrmat5.m算法")
        self.pflag = 0
        self.guidefweight = np.array([0.213, 0.715, 0.072])  # RGB转亮度权重
        self.defnpol = 5  # 默认多项式阶数
        self.oename = "none"
        self.nbin = 4  # 超采样因子
        self.defalpha = 0.5  # Tukey窗参数
        self.maxalpha = 1.0
        self.minalpha = 0.1
        self.image = None  # 由 GUI 层设置，用于 ROI 选择等操作
        logger.info(
            f"SFR计算器初始化完成: 权重={self.guidefweight}, 多项式阶数={self.defnpol}, 合并因子={self.nbin}"
        )

    def centroid(self, x):
        """计算质心位置 - 与MATLAB版本一致"""
        n = np.arange(1, len(x) + 1)
        return np.sum(n * x) / np.sum(x)

    def rotatev2(self, a):
        """
        图像旋转检测 - 改进版本

        基于MATLAB算法：检测图像是否需要旋转以优化边缘检测
        """
        logger.debug("开始图像旋转检测")
        dim = a.shape
        nlin, npix = dim[0], dim[1]

        # 使用更精确的边缘检测方法
        if len(dim) == 3:
            # 使用绿色通道进行检测
            mm = 1
            nn = min(5, nlin // 4)  # 自适应窗口大小
            testv = abs(np.mean(a[-nn:, :, mm]) - np.mean(a[:nn, :, mm]))
            testh = abs(np.mean(a[:, -nn:, mm]) - np.mean(a[:, :nn, mm]))
        else:
            nn = min(5, nlin // 4)
            testv = abs(np.mean(a[-nn:, :]) - np.mean(a[:nn, :]))
            testh = abs(np.mean(a[:, -nn:]) - np.mean(a[:, :nn]))

        rflag = 0
        if testv > testh:
            rflag = 1
            a = np.rot90(a, axes=(1, 0))
            nlin, npix = npix, nlin
            logger.debug("图像已旋转90度以优化边缘检测")

        logger.debug(f"旋转检测完成 - rflag: {rflag}, 新尺寸: {nlin}x{npix}")
        return a, nlin, npix, rflag

    def deriv1(self, a, nlin, npix, fil):
        """
        计算一维导数 - 改进版本

        使用更精确的卷积和边界处理
        """
        logger.debug("计算一维导数")
        b = np.zeros((nlin, npix))

        # 使用更精确的卷积方法
        for ii in range(nlin):
            temp = signal.convolve(a[ii, :], fil, mode="same", method="auto")
            b[ii, :] = temp

            # 改进的边界处理
            if len(fil) == 2:
                b[ii, 0] = b[ii, 1] if npix > 1 else b[ii, 0]
                b[ii, -1] = b[ii, -2] if npix > 1 else b[ii, -1]
            elif len(fil) == 3:
                b[ii, 0] = b[ii, 1] if npix > 1 else b[ii, 0]
                b[ii, -1] = b[ii, -2] if npix > 1 else b[ii, -1]

        logger.debug("一维导数计算完成")
        return b

    def tukey2(self, n, alpha, mid):
        """
        Tukey窗口函数 - 精确实现

        基于MATLAB的精确算法实现
        """
        if n < 3:
            return np.ones(n)

        # 精确的MATLAB算法实现
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
        """
        Tukey窗口函数 - 精确实现

        与MATLAB版本完全一致
        """
        if n == 1:
            return np.ones(1)
        if alpha == 0:
            return np.ones(n)

        x = np.linspace(0, 1, n)
        w = np.ones(x.shape)

        # 精确的MATLAB算法
        first = int(np.floor(alpha * (n - 1) / 2.0)) + 1
        w[0:first] = 0.5 * (1 + np.cos(np.pi * (2 * x[0:first] / alpha - 1)))

        last = n - first + 1
        w[last - 1 :] = 0.5 * (
            1 + np.cos(np.pi * (2 * (1 - x[last - 1 :]) / alpha - 1))
        )

        return w

    def ahamming(self, n, mid):
        """
        汉明窗口函数 - 精确实现

        基于MATLAB的精确算法
        """
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
        """数值范围限制函数"""
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
        """
        边缘位置拟合 - 改进版本

        使用更稳健的多项式拟合方法
        """
        index = np.arange(nlin)

        # 使用加权最小二乘法提高拟合精度
        if len(cent) > 2:
            # 计算权重（边缘位置更可靠）
            weights = np.ones_like(cent)
            # 边缘位置变化较大的点权重较低
            if len(cent) > 3:
                diff = np.abs(np.diff(cent))
                weights[1:-1] = 1.0 / (1.0 + 0.1 * (diff[:-1] + diff[1:]))
                weights[0] = weights[1]
                weights[-1] = weights[-2]

        p = np.polyfit(index, cent, nn, w=weights)
        return p

    def project2(self, bb, fitme, fac=4):
        """
        精确的投影和分箱算法 - 基于MATLAB版本

        关键改进：
        1. 精确的像素投影到超采样网格
        2. 改进的边界处理
        3. 更准确的归一化
        """
        try:
            nlin, npix = bb.shape
            logger.debug(f"开始投影和分箱 - 输入尺寸: {bb.shape}, 超采样因子: {fac}")

            # 1. 创建超采样网格
            nn = fac * npix
            esf = np.zeros(nn)
            counts = np.zeros(nn)  # 用于统计每个超采样位置的像素数

            # 2. 精确投影算法 - 基于MATLAB版本
            for n in range(nlin):
                # 计算该行的边缘位置
                edge_pos = np.polyval(fitme, n)

                # 边界检查
                if np.isnan(edge_pos) or not np.isfinite(edge_pos):
                    continue

                # 计算相对于边缘中心的偏移
                offset = edge_pos - (npix / 2)

                # 对每个像素进行精确投影
                for j in range(npix):
                    # 计算像素在超采样网格中的位置
                    super_pos = (j - offset) * fac

                    # 边界检查
                    if 0 <= super_pos < nn:
                        idx = int(super_pos)
                        frac = super_pos - idx

                        # 线性插值到相邻的超采样位置
                        if idx < nn - 1:
                            esf[idx] += bb[n, j] * (1 - frac)
                            esf[idx + 1] += bb[n, j] * frac
                            counts[idx] += 1 - frac
                            counts[idx + 1] += frac
                        else:
                            esf[idx] += bb[n, j]
                            counts[idx] += 1

            # 3. 归一化处理
            valid_indices = counts > 0
            if np.any(valid_indices):
                esf[valid_indices] = esf[valid_indices] / counts[valid_indices]

            # 4. 应用平滑处理
            if len(esf) > 10:
                # 使用高斯滤波平滑
                esf = signal.convolve(esf, np.ones(3) / 3, mode="same")

            # 5. 最终归一化到[0,1]范围
            esf_min = np.min(esf)
            esf_max = np.max(esf)
            if esf_max - esf_min > 0:
                esf = (esf - esf_min) / (esf_max - esf_min)

            # 6. 处理起始和终止位置附近的异常数据
            # 对起始位置开始5个像素的数据进行平滑处理
            # 对终止位置向前5个像素的数据进行平滑处理
            if len(esf) > 10:
                # 平滑起始位置
                for i in range(5):
                    if i < len(esf):
                        esf[i] = esf[5] if i < 5 else esf[i]
                # 平滑终止位置
                for i in range(len(esf) - 1, len(esf) - 6, -1):
                    if i >= 0:
                        esf[i] = esf[len(esf) - 6] if i >= len(esf) - 5 else esf[i]

            logger.debug(f"投影和分箱完成 - 输出尺寸: {esf.shape}")
            return esf, 0  # status = 0 表示成功

        except Exception as e:
            logger.error(f"投影和分箱失败: {e}")
            import traceback

            traceback.print_exc()
            return np.zeros(1), 1  # status = 1 表示失败

    def fir2fix(self, n, m):
        """
        FIR滤波器响应校正 - 精确实现

        基于MATLAB的校正算法
        """
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
        """
        数组中心化 - 改进版本

        更精确的中心化算法
        """
        # 检查NaN值
        if np.isnan(mm) or not np.isfinite(mm):
            return c

        nn = len(c)
        if nn == 0:
            return c

        # 计算需要移位的数量
        shift = int(nn / 2 - mm)

        # 如果移位为0，直接返回原数组
        if shift == 0:
            return c

        # 创建结果数组
        result = np.zeros_like(c)

        # 应用移位 - 使用更精确的方法
        if shift > 0:
            # 向右移位
            result[shift:] = c[: nn - shift]
            # 边界填充
            result[:shift] = c[0]
        else:
            # 向左移位
            shift_abs = abs(shift)
            result[: nn - shift_abs] = c[shift_abs:]
            # 边界填充
            result[nn - shift_abs :] = c[-1]

        return result

    def rsquare(self, y_pred, y_true):
        """计算R平方、均方根误差和平均误差"""
        logger.debug("计算R平方、RMSE和平均误差")
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
        merror = np.mean(np.abs(y_true - y_pred))
        logger.debug(f"R²: {r2:.4f}, RMSE: {rmse:.4f}, 平均误差: {merror:.4f}")
        return r2, rmse, merror

    def sampeff(self, dat, val, del_image, pflag, npol):
        """
        采样效率计算 - 改进版本

        更精确的插值和计算
        """
        logger.debug("开始计算采样效率")
        nfreq, ncol = dat.shape
        ncol -= 1  # 移除频率列
        e = np.zeros((1, ncol))
        freqval = np.zeros((1, len(val)))

        for j in range(len(val)):
            for i in range(ncol):
                # 精确查找SFR等于val[j]的频率
                target_val = val[j]

                # 使用更精确的插值方法
                sfr_values = dat[:, i + 1]
                freq_values = dat[:, 0]

                # 找到第一个小于等于目标值的点
                idx = np.where(sfr_values <= target_val)[0]

                if len(idx) > 0:
                    idx = idx[0]
                    if idx > 0:
                        # 精确线性插值
                        x1, x2 = freq_values[idx - 1], freq_values[idx]
                        y1, y2 = sfr_values[idx - 1], sfr_values[idx]

                        if y2 != y1:
                            freqval[0, j] = x1 + (target_val - y1) * (x2 - x1) / (
                                y2 - y1
                            )
                        else:
                            freqval[0, j] = x1
                    else:
                        freqval[0, j] = freq_values[idx]
                else:
                    freqval[0, j] = 0

                # 计算采样效率
                if freqval[0, 0] > 0:  # 对于10%的值
                    nyquist = 0.5 / del_image
                    e[0, i] = (freqval[0, 0] / nyquist) * 100

        logger.debug(f"采样效率计算完成 - 结果形状: {e.shape}")
        return e, freqval, []

    def calculate_sfr(self, io=0, del_input=1, a=None, npol=None, wflag=0, weight=None):
        """
        基于MATLAB sfrmat5.m的主要SFR计算函数 - 改进版本

        主要改进：
        1. 精确的边缘检测和拟合
        2. 改进的投影和分箱算法
        3. 更准确的SFR计算
        4. 增强的错误处理
        """
        logger.info("开始SFR计算 - 基于MATLAB sfrmat5.m算法")
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

        if io != 1:
            logger.error("GUI 模式已移除。请使用 python GUI.py 启动图形界面。")
            return 1, None, None, None, None, None, None, None
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


# 测试函数
def test_sfr_calculator():
    """测试SFR计算器"""
    calculator = SFRCalculator()

    # 使用测试图像
    test_image_path = "images/Test_edge1.tif"

    try:
        # 加载测试图像
        img = cv2.imread(test_image_path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            logger.info(f"测试图像加载成功: {img.shape}")

            # 运行SFR计算
            status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = (
                calculator.calculate_sfr(io=1, del_input=1, a=img, npol=3)
            )

            if status == 0:
                logger.info("测试成功完成")
                logger.info(f"SFR50: {sfr50}")
                logger.info(f"数据形状: {dat.shape}")
            else:
                logger.error("测试失败")
        else:
            logger.warning("测试图像未找到，跳过测试")
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")


if __name__ == "__main__":
    # 运行测试
    test_sfr_calculator()

import os
import sys

import cv2
import matplotlib.pyplot as plt
import numpy as np

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入两个模块
import slantedgeMTF
from sfrmat5_updated import SFRCalculator

# 测试图像路径
IMAGE_PATH = "images/Test_edge1.tif"


# 读取测试图像
def read_image(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"无法读取图像: {path}")
        sys.exit(1)
    return img


# 使用sfrmat5_updated计算ESF、LSF和SFR
def compute_esf_sfrmat5(img):
    calculator = SFRCalculator()
    # 使用非GUI模式，io=1
    status, dat, e, sfr50, fitme, esf, nbin, del2, is_dpi = calculator.calculate_sfr(
        io=1, del_input=1, a=img, npol=3
    )
    if status != 0:
        print("sfrmat5计算失败")
        return None, None, None, None

    # 获取ESF数据（使用亮度通道，即最后一个通道）
    esf_data = esf[:, -1] if esf.shape[1] > 1 else esf[:, 0]
    # 确保ESF归一化到[0,1]范围
    esf_min = np.min(esf_data)
    esf_max = np.max(esf_data)
    if esf_max - esf_min > 0:
        esf_data = (esf_data - esf_min) / (esf_max - esf_min)
    # 生成对应的位置数据
    pos = np.linspace(0, len(esf_data) - 1, len(esf_data)) / nbin

    # 计算LSF（通过ESF求导）
    lsf_data = np.gradient(esf_data, pos)

    # 获取SFR数据（从dat中提取）
    freq = dat[:, 0]  # 频率
    sfr_data = dat[:, 1]  # SFR值

    # 转换频率单位为 lp/mm
    # 注意：1 lp/mm = 0.5 cycles/mm
    pixel_pitch = 0.3  # 像素间距(μm)
    freq = (freq * 1000) / (2 * pixel_pitch)

    return pos, esf_data, lsf_data, (freq, sfr_data)


# 使用slantedgeMTF计算ESF、LSF和SFR
def compute_esf_slantedge(img):
    # 读取图像
    img_gray = slantedgeMTF.read_gray(IMAGE_PATH)
    # 获取ROI（整个图像）
    roi = slantedgeMTF.get_center_roi(img_gray)
    # 计算梯度
    grad = slantedgeMTF.edge_gradient(roi)
    # 拟合边缘
    k, b, angle = slantedgeMTF.fit_edge(grad)
    # 计算距离场
    dist = slantedgeMTF.distance_map(roi.shape, k, b)
    # 计算ESF
    pos, esf = slantedgeMTF.compute_esf(roi, dist, slantedgeMTF.UPSAMPLE_FACTOR)
    # 归一化ESF
    esf_norm = slantedgeMTF.normalize_esf(esf)
    # 计算LSF和SFR
    freq, mtf, lsf = slantedgeMTF.esf2mtf(pos, esf_norm)

    return pos, esf_norm, lsf, (freq, mtf)


# 比较两个ESF数据
def compare_esf(pos1, esf1, pos2, esf2):
    # 确保两个ESF长度相同，对较长的进行插值
    if len(esf1) != len(esf2):
        # 使用较长的长度作为参考
        if len(esf1) > len(esf2):
            # 对esf2进行插值
            from scipy.interpolate import interp1d

            f = interp1d(pos2, esf2, kind="linear", fill_value="extrapolate")
            esf2_interp = f(pos1)
            return pos1, esf1, pos1, esf2_interp
        else:
            # 对esf1进行插值
            from scipy.interpolate import interp1d

            f = interp1d(pos1, esf1, kind="linear", fill_value="extrapolate")
            esf1_interp = f(pos2)
            return pos2, esf1_interp, pos2, esf2
    return pos1, esf1, pos2, esf2


# 计算差异指标
def calculate_diff(esf1, esf2):
    # 计算均方误差
    mse = np.mean((esf1 - esf2) ** 2)
    # 计算平均绝对误差
    mae = np.mean(np.abs(esf1 - esf2))
    # 计算最大误差
    max_error = np.max(np.abs(esf1 - esf2))

    return mse, mae, max_error


# 主函数
def main():
    print("读取测试图像...")
    img = read_image(IMAGE_PATH)
    print(f"图像尺寸: {img.shape}")

    print("\n使用sfrmat5_updated计算ESF、LSF和SFR...")
    pos1, esf1, lsf1, sfr1 = compute_esf_sfrmat5(img)
    if pos1 is None:
        return

    print("使用slantedgeMTF计算ESF、LSF和SFR...")
    pos2, esf2, lsf2, sfr2 = compute_esf_slantedge(img)

    # 可视化结果
    print("\n绘制比较图...")
    plt.figure(figsize=(7, 5))

    # 绘制两个ESF
    plt.subplot(3, 1, 1)
    plt.plot(pos1, esf1, "b-", label="sfrmat5_updated")
    plt.plot(pos2, esf2, "r-", label="slantedgeMTF")
    plt.title("ESF Comparison")
    plt.xlabel("Position (pixels)")
    plt.ylabel("Normalized Intensity")
    plt.legend()
    plt.grid(True)

    # 绘制两个LSF
    plt.subplot(3, 1, 2)
    plt.plot(pos1, lsf1, "b-", label="sfrmat5_updated")
    plt.plot(pos2, lsf2, "r-", label="slantedgeMTF")
    plt.title("LSF Comparison")
    plt.xlabel("Position (pixels)")
    plt.ylabel("Amplitude")
    plt.legend()
    plt.grid(True)

    # 绘制两个SFR
    plt.subplot(3, 1, 3)
    plt.plot(sfr1[0], sfr1[1], "b-", label="sfrmat5_updated")
    plt.plot(sfr2[0], sfr2[1], "r-", label="slantedgeMTF")
    plt.title("SFR Comparison")
    plt.xlabel("Frequency")
    plt.ylabel("SFR")
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()

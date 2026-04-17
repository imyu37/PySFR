import cv2
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import savgol_filter

# ===================== 参数 =====================
UPSAMPLE_FACTOR = 4
SMOOTH_WINDOW = 9
PIXEL_PITCH = 0.3  # 像素间距(μm)，用于显示lp/mm，不知道就填1


# ===================== 1. 读取与ROI =====================
def read_gray(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return img.astype(np.float32)


def get_center_roi(img, size=None):
    # 如果没有指定size，返回整个图像
    if size is None:
        return img
    # 否则返回指定大小的中心区域
    h, w = img.shape
    cy, cx = h // 2, w // 2
    half = size // 2
    return img[cy - half : cy + half, cx - half : cx + half]


# ===================== 2. 拟合边缘 & 距离场 =====================
def edge_gradient(roi):
    gx = cv2.Sobel(roi, cv2.CV_32F, 1, 0, 3)
    gy = cv2.Sobel(roi, cv2.CV_32F, 0, 1, 3)
    mag = np.hypot(gx, gy)
    return mag


def fit_edge(roi_grad):
    # 找到梯度最大值的位置
    y, x = np.where(roi_grad == np.max(roi_grad))
    # 如果点太少，使用梯度较大的区域
    if len(x) < 2:
        # 找到梯度较大的区域
        threshold = np.max(roi_grad) * 0.8
        y, x = np.where(roi_grad >= threshold)
    # 随机采样10个点以提高稳定性
    if len(x) > 10:
        indices = np.random.choice(len(x), 10, replace=False)
        x = x[indices]
        y = y[indices]
    # 使用稳健的拟合方法
    k, b = np.polyfit(x, y, 1)
    angle = np.degrees(np.arctan(k))
    return k, b, abs(angle)


def distance_map(shape, k, b):
    h, w = shape
    x = np.arange(w)
    y = np.arange(h)
    xv, yv = np.meshgrid(x, y)
    dist = (k * xv - yv + b) / np.sqrt(k**2 + 1)
    return dist


# ===================== 3. 计算 ESF =====================
def compute_esf(roi, dist, upsample):
    d = dist * upsample
    bins = np.arange(np.floor(d.min()), np.ceil(d.max()) + 1)
    pos, esf = [], []
    for l, r in zip(bins[:-1], bins[1:]):
        mask = (d >= l) & (d < r)
        if np.any(mask):
            esf.append(np.mean(roi[mask]))
            pos.append((l + r) / 2)
    pos = np.array(pos) / upsample
    esf = np.array(esf)
    esf = savgol_filter(esf, SMOOTH_WINDOW, 3)
    return pos, esf


def normalize_esf(esf):
    return (esf - esf.min()) / (esf.max() - esf.min())


# ===================== 4. ESF → LSF → MTF =====================
def esf2mtf(pos, esf_norm):
    # 1) 求导得到 LSF
    lsf = np.gradient(esf_norm, pos)
    lsf = savgol_filter(lsf, SMOOTH_WINDOW, 3)

    # 2) 补零，让FFT更干净
    n = len(lsf)
    fft_lsf = np.fft.fft(lsf, n * 4)
    # 3) 取模并归一化得到 MTF
    mtf = np.abs(fft_lsf)
    mtf = mtf / mtf[0]

    # 4) 频率轴（cycles/pixel）
    mtf = mtf[: len(mtf) // 2]
    # 计算频率轴
    freq_pixel = np.fft.fftfreq(n * 4, pos[1] - pos[0])[: len(mtf)]
    # 转换为 lp/mm (线对/毫米)
    # 注意：1 lp/mm = 0.5 cycles/mm
    freq = (freq_pixel / (PIXEL_PITCH / 1000)) / 2

    return freq, mtf, lsf


# ===================== 主函数 =====================
if __name__ == "__main__":
    IMAGE_PATH = "images/Test_edge1.tif"

    img = read_gray(IMAGE_PATH)
    roi = get_center_roi(img)  # 使用整个图像

    grad = edge_gradient(roi)
    k, b, angle = fit_edge(grad)
    dist = distance_map(roi.shape, k, b)
    pos, esf = compute_esf(roi, dist, UPSAMPLE_FACTOR)
    esf_norm = normalize_esf(esf)

    # 核心：ESF 算 MTF
    freq, mtf, lsf = esf2mtf(pos, esf_norm)

    print(f"边缘角度: {angle:.2f}°")
    print(f"MTF50 位置: {freq[np.argmin(np.abs(mtf - 0.5))]:.3f} lp/mm")

    # 画图
    plt.figure(figsize=(14, 9))

    plt.subplot(2, 2, 1)
    plt.imshow(roi, cmap="gray")
    plt.title("ROI")

    plt.subplot(2, 2, 2)
    plt.plot(pos, esf_norm, "b-")
    plt.title("ESF")
    plt.grid(True)

    plt.subplot(2, 2, 3)
    plt.plot(pos, lsf, "r-")
    plt.title("LSF")
    plt.grid(True)

    plt.subplot(2, 2, 4)
    plt.plot(freq, mtf, "g-", linewidth=2)
    plt.title("MTF")
    plt.xlabel("lp/mm")
    plt.ylabel("MTF")
    plt.grid(True)
    plt.ylim(0, 1.05)

    plt.tight_layout()
    plt.show()

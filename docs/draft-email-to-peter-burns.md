# 致 Peter Burns 的邮件草稿

**收件人**: pdburns@ieee.org
**主题**: Request for Permission - Python Port of sfrmat5.m (PySFR Project)

---

Dear Dr. Burns,

I hope this message finds you well. My name is [你的姓名], and I am writing to seek your permission regarding a Python port of your MATLAB `sfrmat5.m` code, which I understand you developed and distributed in support of ISO 12233 Edition 4.

## Background

I have developed a Python implementation called **PySFR**, which faithfully ports the slanted-edge SFR/MTF measurement algorithm from your `sfrmat5.m` to Python. The project:

- Follows the original algorithmic pipeline closely (edge projection → polynomial fitting → ESF → LSF → SFR)
- Adds a desktop GUI using FreeSimpleGUI with matplotlib-based ROI selection
- Supports cross-platform operation (Windows, macOS, Linux)
- Includes the original MATLAB `sfrmat5.m` files in a `ref/` directory with full attribution

The project is currently hosted locally and intended for **non-commercial, academic/research use** in optical system evaluation and image quality analysis.

## What I Am Requesting

I would like to ask for your explicit permission to:

1. **Distribute the Python port** as an open-source project (potentially on GitHub or similar platforms)
2. **Choose an appropriate open-source license** for the Python code (such as MIT or BSD-3-Clause)
3. **Keep the attribution** to you as the original algorithm author, both in the source code and documentation
4. **Include the original MATLAB `sfrmat5.m`** files in the `ref/` directory for reference, with your copyright notices intact

## Attribution

The project README (both Chinese and English) already includes:

```
- 原始 MATLAB 版本: Peter Burns, pdburns@ieee.org
- Original MATLAB code copyright:
  - Author: Peter Burns, pdburns@ieee.org
  - Based on sfrmat4, adapted with polynomial edge fitting
  - Last updated: February 27, 2023
  - Supports ISO 12233 4th edition
```

I am fully committed to preserving proper attribution and respecting your intellectual property rights.

If you have specific requirements for how the code or algorithm should be credited, licensed, or distributed, please let me know and I will follow them.

## Next Steps

If you grant permission:
- I will add a formal LICENSE file to the project
- I will include your preferred copyright notice and attribution format
- I am happy to send you a link to the project if you'd like to review it

If you do not wish for a Python port to be distributed, I will respect that decision and keep the project strictly for personal use only.

Thank you very much for your time and for making `sfrmat5.m` available to the community. Your work has been invaluable to those of us working in optical metrology and image quality evaluation.

Best regards,

[你的姓名]
[你的邮箱]
[日期]

---

## 附注（非邮件内容）

- 如 Peter Burns 回复同意，转至优先级 2
- 如 Peter Burns 回复拒绝，停止公开分发，仅限个人使用，并从公开仓库移除
- 如 30 天内无回复，建议保守处理（不在 GitHub 等平台公开发布），但可继续个人使用

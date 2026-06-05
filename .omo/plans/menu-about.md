# 菜单栏"帮助"→"关于"

## TL;DR
> **Summary**: 将菜单栏「帮助」替换为「关于」，点击后直接弹出包含版本信息的窗口
> **Deliverables**: 1 处 GUI.py 菜单定义修改
> **Effort**: Quick
> **Parallel**: NO

## TODOs

- [x] 1. GUI.py: 将菜单定义从 `["帮助", ["关于"]]` 改为 `["关于"]`

  **What to do**:
  - 在 `SFRGUI.create_layout()` 中，将 `sg.Menu` 的传入参数从
    ```python
    [["帮助", [["关于"]]]]
    ```
    改为
    ```python
    [["关于"]]
    ```
  - 无需修改事件处理。`elif event == "关于": self.show_about_dialog()` 已存在且 `show_about_dialog()` 内容已包含"版本信息"（版本号、算法来源、联系方式等）。

  **Must NOT do**:
  - 不要修改 `show_about_dialog()` 的内容
  - 不要修改其他任何事件处理逻辑

  **References**:
  - GUI.py: `SFRGUI.create_layout()` 第 58-76 行 — 菜单布局定义
  - GUI.py: `SFRGUI.show_about_dialog()` 第 298-323 行 — 关于对话框，已包含版本信息
  - GUI.py: 事件循环第 639 行 — `elif event == "关于":` 处理

  **Acceptance Criteria**:
  - [ ] 启动 GUI 后菜单栏显示「关于」而非「帮助」
  - [ ] 点击「关于」直接弹出窗口，标题为「关于」，内容包含「版本信息」
  - [ ] 不出现下拉子菜单（点击直接弹出，无需二次点击）

  **QA Scenarios**:
  ```
  Scenario: 点击 "关于" 弹出版本信息
    Tool: interactive_bash
    Steps:
      1. python GUI.py 启动
      2. 点击菜单栏 "关于"
    Expected: 弹出窗口标题为 "关于"，内容包含 "版本信息:"
    Evidence: .omo/evidence/task-1-about-dialog.png

  Scenario: 菜单栏不显示 "帮助"
    Tool: Bash
    Steps: grep -n "帮助" GUI.py
    Expected: 无匹配结果（仅出现在正常被移除）
    Evidence: .omo/evidence/task-1-no-help.txt
  ```

  **Commit**: YES | Message: `fix(GUI): 将菜单栏"帮助"替换为"关于"，点击直接弹出版本信息` | Files: [`GUI.py`]

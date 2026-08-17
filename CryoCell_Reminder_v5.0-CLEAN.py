# CryoCell_Reminder_v5.0_!final!

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import sqlite3
import datetime
import threading
import time
import schedule
import smtplib
import json
import base64
import sys
import os
import re
from email.mime.text import MIMEText

# 获取当前脚本所在目录的绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
running = True
reminder_send_lock = threading.Lock()
scheduler_thread = None
manual_reminder_button = None

#--------------------------------------------
def get_app_dir():
    """返回应用数据存储目录"""
    if getattr(sys, 'frozen', False):
        # 打包环境：使用exe所在目录
        return os.path.dirname(sys.executable)
    else:
        # 开发环境：使用脚本所在目录
        return os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path):
    """返回资源文件的完整路径"""
    base_dir = get_app_dir()
    return os.path.join(base_dir, relative_path)


DB_PATH = resource_path("cell_freeze.db")
CONFIG_FILE = resource_path("email_config.json")
THEME_CONFIG_FILE = resource_path("theme_config.json")

# ------------------ 统一视觉与窗口适配 ------------------
FONT_FAMILY = "Segoe UI"
FORM_TEXT_WIDTH = 28
FORM_EMAIL_WIDTH = 34
FORM_SHORT_WIDTH = 8
FORM_COMBO_WIDTH = 30
THEMES = {
    "light": {
        "label": "清爽浅色", "bg": "#f5f5f7", "card": "#ffffff",
        "text": "#1d1d1f", "secondary": "#6e6e73",
        "accent": "#007aff", "accent_dark": "#005ecb",
        "border": "#e5e5ea", "hover": "#edf5ff", "pressed": "#d9eaff",
        "heading": "#ececf0", "occupied": "#eaf3ff", "occupied_text": "#174a7e",
        "empty_text": "#8e8e93", "primary_text": "#ffffff",
        "success": "#34c759", "danger": "#ff3b30",
    },
    "pink": {
        "label": "淡粉柔和", "bg": "#fff5f8", "card": "#fffafd",
        "text": "#4a2d3b", "secondary": "#8c6678",
        "accent": "#d96c99", "accent_dark": "#b94f7a",
        "border": "#f0cfdd", "hover": "#fdebf2", "pressed": "#f8d7e4",
        "heading": "#f7dfe9", "occupied": "#fbe6ef", "occupied_text": "#82435f",
        "empty_text": "#a47b8d", "primary_text": "#ffffff",
        "success": "#4fae7b", "danger": "#e34f67",
    },
    "dark": {
        "label": "暗黑模式", "bg": "#1c1c1e", "card": "#2c2c2e",
        "text": "#f5f5f7", "secondary": "#a1a1a6",
        "accent": "#0a84ff", "accent_dark": "#006edc",
        "border": "#48484a", "hover": "#333f4d", "pressed": "#294563",
        "heading": "#3a3a3c", "occupied": "#22364b", "occupied_text": "#9acbff",
        "empty_text": "#98989d", "primary_text": "#ffffff",
        "success": "#30d158", "danger": "#ff453a",
    },
    "brown": {
        "label": "2048 棕色", "bg": "#faf8ef", "card": "#eee4da",
        "text": "#776e65", "secondary": "#776e65",
        "accent": "#8f7a66", "accent_dark": "#776e65",
        "border": "#bbada0", "hover": "#ede0c8", "pressed": "#d8c7b5",
        "heading": "#d8c7b5", "occupied": "#ede0c8", "occupied_text": "#5f574f",
        "empty_text": "#9f8f80", "primary_text": "#ffffff",
        "success": "#7fa650", "danger": "#c96b56",
    },
}
CURRENT_THEME = "light"


def set_theme_palette(theme_name):
    global CURRENT_THEME, APP_BG, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY
    global ACCENT, ACCENT_DARK, SUCCESS, DANGER, BORDER_COLOR
    global HOVER_BG, PRESSED_BG, HEADING_BG, OCCUPIED_BG, OCCUPIED_TEXT
    global EMPTY_TEXT, PRIMARY_TEXT
    CURRENT_THEME = theme_name if theme_name in THEMES else "light"
    palette = THEMES[CURRENT_THEME]
    APP_BG = palette["bg"]
    CARD_BG = palette["card"]
    TEXT_PRIMARY = palette["text"]
    TEXT_SECONDARY = palette["secondary"]
    ACCENT = palette["accent"]
    ACCENT_DARK = palette["accent_dark"]
    SUCCESS = palette["success"]
    DANGER = palette["danger"]
    BORDER_COLOR = palette["border"]
    HOVER_BG = palette["hover"]
    PRESSED_BG = palette["pressed"]
    HEADING_BG = palette["heading"]
    OCCUPIED_BG = palette["occupied"]
    OCCUPIED_TEXT = palette["occupied_text"]
    EMPTY_TEXT = palette["empty_text"]
    PRIMARY_TEXT = palette["primary_text"]


def load_theme_preference():
    try:
        with open(THEME_CONFIG_FILE, "r", encoding="utf-8") as file:
            theme_name = json.load(file).get("theme", "light")
            return theme_name if theme_name in THEMES else "light"
    except (OSError, ValueError, AttributeError):
        return "light"


def save_theme_preference(theme_name):
    try:
        with open(THEME_CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump({"theme": theme_name}, file, ensure_ascii=False, indent=2)
    except OSError:
        pass


set_theme_palette("light")


def fit_window(win, preferred_width, preferred_height, min_width=320, min_height=180):
    """按当前屏幕可用范围限制窗口尺寸并居中，避免内容落到屏幕外。"""
    # Toplevel/Tk 创建后默认会先映射到屏幕左上角。先隐藏，再计算尺寸，
    # 等当前窗口的控件全部创建完毕后一次性显示，可消除左上角首帧闪烁。
    win.withdraw()
    win.update_idletasks()
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    max_width = max(320, screen_width - 48)
    # 为任务栏、标题栏和屏幕边缘保留空间。
    max_height = max(240, screen_height - 96)
    width = min(preferred_width, max_width)
    height = min(preferred_height, max_height)
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2 - 12)
    win.geometry(f"{width}x{height}+{x}+{y}")
    win.minsize(min(min_width, width), min(min_height, height))
    win.resizable(True, True)
    win.after_idle(lambda target=win: reveal_fitted_window(target))


def create_hidden_toplevel(parent=None):
    """创建时立即隐藏正式窗口，避免任何主题或布局操作触发左上角首帧。"""
    window = tk.Toplevel(parent)
    window.withdraw()
    return window


def reveal_fitted_window(win):
    """在窗口完成布局后，将其直接显示在已经计算好的位置。"""
    try:
        if not win.winfo_exists():
            return
        win.deiconify()
        # Windows 可能拒绝普通 lift() 抢回前台。短暂置顶后立即恢复，
        # 既保证刚打开的窗口可见，也不会让它长期压住其他程序。
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        win.lift()
        win.focus_force()
        win.after(120, lambda target=win: release_temporary_topmost(target))
    except tk.TclError:
        pass


def release_temporary_topmost(win):
    try:
        if win.winfo_exists():
            win.attributes("-topmost", False)
    except tk.TclError:
        pass


def apply_modern_theme(win):
    """应用统一、简洁且高对比度的现代界面样式。"""
    win.configure(bg=APP_BG)
    win.option_add("*Font", (FONT_FAMILY, 10))
    win.option_add("*Background", APP_BG)
    win.option_add("*Foreground", TEXT_PRIMARY)
    win.option_add("*Entry.Background", CARD_BG)
    win.option_add("*Entry.Foreground", TEXT_PRIMARY)
    style = ttk.Style(win)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    remove_dotted_button_focus(style)
    style.configure(".", font=(FONT_FAMILY, 10), background=APP_BG, foreground=TEXT_PRIMARY)
    style.configure("TFrame", background=APP_BG)
    style.configure("Card.TFrame", background=CARD_BG)
    style.configure("TLabel", background=APP_BG, foreground=TEXT_PRIMARY)
    style.configure(
        "TButton", background=CARD_BG, foreground=ACCENT, padding=(12, 7),
        borderwidth=1, bordercolor=BORDER_COLOR, lightcolor=BORDER_COLOR,
        darkcolor=BORDER_COLOR, relief="flat", font=(FONT_FAMILY, 10, "bold")
    )
    style.map(
        "TButton",
        background=[("pressed", PRESSED_BG), ("active", HOVER_BG)],
        foreground=[("disabled", TEXT_SECONDARY), ("pressed", ACCENT_DARK), ("active", ACCENT_DARK)],
        bordercolor=[("focus", ACCENT), ("pressed", ACCENT_DARK), ("active", ACCENT)]
    )
    style.configure(
        "Primary.TButton", background=ACCENT, foreground=PRIMARY_TEXT,
        bordercolor=ACCENT, padding=(14, 8)
    )
    style.map(
        "Primary.TButton",
        background=[("pressed", ACCENT_DARK), ("active", ACCENT)],
        foreground=[("pressed", PRIMARY_TEXT), ("active", PRIMARY_TEXT)]
    )
    style.configure(
        "Recording.TButton", background=DANGER, foreground=PRIMARY_TEXT,
        bordercolor=DANGER, padding=(14, 8)
    )
    style.map(
        "Recording.TButton",
        background=[("pressed", "#d92c23"), ("active", "#ff5a52")],
        foreground=[("pressed", PRIMARY_TEXT), ("active", PRIMARY_TEXT)]
    )
    style.configure(
        "TCombobox", fieldbackground=CARD_BG, background=CARD_BG,
        foreground=TEXT_PRIMARY, arrowcolor=TEXT_SECONDARY, bordercolor=BORDER_COLOR, padding=5
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", CARD_BG)],
        foreground=[("readonly", TEXT_PRIMARY)],
        selectbackground=[("readonly", ACCENT)],
        selectforeground=[("readonly", PRIMARY_TEXT)]
    )
    style.configure(
        "TScrollbar", background=HEADING_BG, troughcolor=APP_BG,
        bordercolor=APP_BG, arrowcolor=TEXT_SECONDARY
    )
    style.configure(
        "Treeview", background=CARD_BG, fieldbackground=CARD_BG,
        foreground=TEXT_PRIMARY, rowheight=30, borderwidth=0
    )
    style.configure(
        "Treeview.Heading", background=HEADING_BG, foreground=TEXT_PRIMARY,
        relief="flat", padding=(8, 8), font=(FONT_FAMILY, 10, "bold")
    )
    style.configure("Treeview.Heading", background=HEADING_BG)
    style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", PRIMARY_TEXT)])
    configure_box_grid_styles(style)
    return style


def remove_dotted_button_focus(style):
    """移除 clam 主题的点状焦点元素，保留由 bordercolor 表达的柔和焦点。"""
    def without_focus(layout):
        cleaned = []
        for element_name, options in layout:
            options = dict(options)
            children = without_focus(options.get("children", []))
            if element_name.endswith(".focus"):
                cleaned.extend(children)
                continue
            if "children" in options:
                options["children"] = children
            cleaned.append((element_name, options))
        return cleaned

    try:
        style.layout("TButton", without_focus(style.layout("TButton")))
    except tk.TclError:
        pass


def install_button_focus_behavior(win):
    """鼠标点击不残留焦点框；Tab 键导航仍保留主题色边框。"""
    def clear_mouse_focus(event):
        widget = event.widget

        def clear():
            try:
                # 如果按钮刚打开了新窗口，焦点已经转移，不能再抢回主窗口。
                if widget.winfo_exists() and widget.focus_get() is widget:
                    widget.winfo_toplevel().focus_set()
            except tk.TclError:
                pass

        widget.after_idle(clear)

    win.bind_class("TButton", "<ButtonRelease-1>", clear_mouse_focus, add="+")


def configure_box_grid_styles(style):
    """同步冻存盒格子的主题色，同时保留拖拽动作的语义色。"""
    style.configure(
        "Occupied.TButton", background=OCCUPIED_BG, foreground=OCCUPIED_TEXT,
        padding=2, font=(FONT_FAMILY, 9, "bold")
    )
    style.configure(
        "Empty.TButton", background=CARD_BG, foreground=EMPTY_TEXT,
        padding=2, font=(FONT_FAMILY, 9)
    )
    style.configure(
        "Selected.TButton", background=ACCENT, foreground=PRIMARY_TEXT,
        bordercolor=ACCENT_DARK, lightcolor=ACCENT, darkcolor=ACCENT_DARK,
        borderwidth=3, relief="solid", font=(FONT_FAMILY, 9, "bold")
    )
    style.map(
        "Selected.TButton",
        background=[("pressed", ACCENT_DARK), ("active", ACCENT), ("focus", ACCENT)],
        foreground=[("pressed", PRIMARY_TEXT), ("active", PRIMARY_TEXT), ("focus", PRIMARY_TEXT)]
    )
    style.configure("DragSource.TButton", background="#ffd9a0", foreground="#5c3700", padding=2, font=(FONT_FAMILY, 9, "bold"))
    style.configure("DragSourcePulse.TButton", background="#ff9f0a", foreground="#3e2723", padding=2, font=(FONT_FAMILY, 9, "bold"))
    style.configure("DropTarget.TButton", background="#b9ebc6", foreground="#145c2a", padding=2, font=(FONT_FAMILY, 9, "bold"))


def recolor_widget_tree(widget, old_palette):
    """将已经打开的 Tk 控件从旧色板映射到当前色板。"""
    old_bg = old_palette["bg"]
    old_card = old_palette["card"]
    background_map = {
        old_bg.lower(): APP_BG,
        old_card.lower(): CARD_BG,
        old_palette["accent"].lower(): ACCENT,
        old_palette["heading"].lower(): HEADING_BG,
        old_palette["occupied"].lower(): OCCUPIED_BG,
        old_palette["border"].lower(): BORDER_COLOR,
    }
    foreground_map = {
        old_palette["text"].lower(): TEXT_PRIMARY,
        old_palette["secondary"].lower(): TEXT_SECONDARY,
        old_palette["accent"].lower(): ACCENT,
        old_palette["danger"].lower(): DANGER,
        old_palette["primary_text"].lower(): PRIMARY_TEXT,
    }
    try:
        if isinstance(widget, (tk.Tk, tk.Toplevel)):
            widget.configure(bg=APP_BG)
        elif isinstance(widget, tk.Menu):
            widget.configure(
                bg=CARD_BG, fg=TEXT_PRIMARY, activebackground=ACCENT,
                activeforeground=PRIMARY_TEXT, bd=0
            )
        else:
            try:
                current_bg = str(widget.cget("bg")).lower()
                if current_bg in background_map:
                    widget.configure(bg=background_map[current_bg])
            except tk.TclError:
                pass
            try:
                current_fg = str(widget.cget("fg")).lower()
                if current_fg in foreground_map:
                    widget.configure(fg=foreground_map[current_fg])
            except tk.TclError:
                pass
            try:
                current_highlight = str(widget.cget("highlightbackground")).lower()
                if current_highlight == old_palette["border"].lower():
                    widget.configure(highlightbackground=BORDER_COLOR)
            except tk.TclError:
                pass
            if isinstance(widget, tk.Entry):
                widget.configure(
                    bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                    highlightbackground=BORDER_COLOR, highlightcolor=ACCENT
                )
            elif isinstance(widget, tk.Button):
                widget.configure(activebackground=HOVER_BG, activeforeground=ACCENT_DARK)
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        recolor_widget_tree(child, old_palette)


def switch_theme(theme_name, win):
    """即时切换所有已打开窗口，并保存下次启动时使用的主题。"""
    old_palette = THEMES[CURRENT_THEME]
    set_theme_palette(theme_name)
    save_theme_preference(CURRENT_THEME)
    apply_modern_theme(win)
    recolor_widget_tree(win, old_palette)
    notify_theme_changed(win)


def notify_theme_changed(widget):
    """通知需要自行重绘内容的窗口（例如 Canvas）同步主题。"""
    try:
        if isinstance(widget, (tk.Tk, tk.Toplevel)):
            widget.event_generate("<<ThemeChanged>>", when="tail")
        for child in widget.winfo_children():
            notify_theme_changed(child)
    except tk.TclError:
        pass


def show_themed_dialog(kind, title, message, parent=None):
    """使用应用主题显示提示与确认弹窗，并保持 messagebox 的返回语义。"""
    parent = parent or globals().get("root") or tk._default_root
    try:
        focused = parent.focus_get() if parent else None
        if focused and isinstance(focused.winfo_toplevel(), tk.Toplevel):
            parent = focused.winfo_toplevel()
    except tk.TclError:
        pass
    if parent is None:
        return None

    dialog = create_hidden_toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.resizable(False, False)
    apply_modern_theme(dialog)

    result = {"value": None}
    symbols = {
        "info": ("i", ACCENT),
        "warning": ("!", "#ff9f0a"),
        "error": ("×", DANGER),
        "question": ("?", ACCENT),
    }
    symbol_kind = "question" if kind in ("yesno", "okcancel", "yesnocancel") else kind
    symbol, symbol_color = symbols.get(symbol_kind, symbols["info"])

    card = tk.Frame(
        dialog, bg=CARD_BG, padx=22, pady=20,
        highlightthickness=1, highlightbackground=BORDER_COLOR
    )
    card.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
    card.columnconfigure(1, weight=1)

    tk.Label(
        card, text=symbol, bg=symbol_color, fg=PRIMARY_TEXT,
        width=2, height=1, font=(FONT_FAMILY, 16, "bold")
    ).grid(row=0, column=0, padx=(0, 14), sticky="n")
    tk.Label(
        card, text=str(message), bg=CARD_BG, fg=TEXT_PRIMARY,
        justify=tk.LEFT, anchor="w", wraplength=440,
        font=(FONT_FAMILY, 10)
    ).grid(row=0, column=1, sticky="ew")

    button_frame = tk.Frame(card, bg=CARD_BG)
    button_frame.grid(row=1, column=0, columnspan=2, sticky="e", pady=(20, 0))

    if kind == "yesno":
        buttons = (("否", False, "TButton"), ("是", True, "Primary.TButton"))
        close_value = False
    elif kind == "okcancel":
        buttons = (("取消", False, "TButton"), ("确定", True, "Primary.TButton"))
        close_value = False
    elif kind == "yesnocancel":
        buttons = (
            ("取消", None, "TButton"),
            ("否", False, "TButton"),
            ("是", True, "Primary.TButton"),
        )
        close_value = None
    else:
        buttons = (("确定", "ok", "Primary.TButton"),)
        close_value = "ok"

    def finish(value):
        result["value"] = value
        try:
            dialog.grab_release()
        except tk.TclError:
            pass
        dialog.destroy()

    for label, value, style_name in buttons:
        ttk.Button(
            button_frame, text=label, style=style_name,
            command=lambda selected=value: finish(selected)
        ).pack(side=tk.LEFT, padx=(7, 0))

    dialog.protocol("WM_DELETE_WINDOW", lambda: finish(close_value))
    dialog.bind("<Escape>", lambda event: finish(close_value))
    dialog.bind("<Return>", lambda event: finish(buttons[-1][1]))
    dialog.update_idletasks()
    fit_window(
        dialog, 520, max(190, min(dialog.winfo_reqheight() + 36, 420)),
        400, 180
    )
    dialog.grab_set()
    dialog.focus_force()
    dialog.wait_window()
    return result["value"]


def install_themed_messageboxes():
    """让程序运行期间的标准提示调用统一使用当前主题。"""
    messagebox.showinfo = lambda title, message, **kwargs: show_themed_dialog(
        "info", title, message, kwargs.get("parent")
    )
    messagebox.showwarning = lambda title, message, **kwargs: show_themed_dialog(
        "warning", title, message, kwargs.get("parent")
    )
    messagebox.showerror = lambda title, message, **kwargs: show_themed_dialog(
        "error", title, message, kwargs.get("parent")
    )
    messagebox.askyesno = lambda title, message, **kwargs: show_themed_dialog(
        "yesno", title, message, kwargs.get("parent")
    )
    messagebox.askokcancel = lambda title, message, **kwargs: show_themed_dialog(
        "okcancel", title, message, kwargs.get("parent")
    )
    messagebox.askyesnocancel = lambda title, message, **kwargs: show_themed_dialog(
        "yesnocancel", title, message, kwargs.get("parent")
    )


# ------------------ 配置管理 ------------------
def load_email_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if "EMAIL_PASSWORD" in data:
            data["EMAIL_PASSWORD"] = base64.b64decode(data["EMAIL_PASSWORD"]).decode("utf-8")
        return data

def email_reminders_enabled(config=None):
    """旧配置默认视为已启用；新配置可明确关闭邮件提醒。"""
    config = load_email_config() if config is None else config
    if not config or config.get("EMAIL_ENABLED", True) is False:
        return False
    return all(config.get(key) for key in ("EMAIL_USER", "EMAIL_RECEIVER", "EMAIL_PASSWORD"))

def save_email_config(email_user, email_receiver, email_password):
    data = {
        "EMAIL_ENABLED": True,
        "EMAIL_USER": email_user,
        "EMAIL_RECEIVER": email_receiver,
        "EMAIL_PASSWORD": base64.b64encode(email_password.encode("utf-8")).decode("utf-8")
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def save_email_disabled():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"EMAIL_ENABLED": False}, f, indent=4)

# ------------------ 邮箱信息输入 ------------------
def ask_email_info():
    temp_root = tk.Tk()
    temp_root.withdraw()  # 🔥 把Tk主窗口隐藏（不显示）

    popup = create_hidden_toplevel(temp_root)
    popup.title("设置邮箱账号")
    apply_modern_theme(popup)
    fit_window(popup, 480, 330, 360, 280)

    font_label = (FONT_FAMILY, 11)

    frame = tk.Frame(popup, bg=APP_BG, padx=24, pady=24)
    frame.pack(fill=tk.BOTH, expand=True)
    frame.columnconfigure(1, weight=1)

    tk.Label(frame, text="发件人邮箱:", bg=APP_BG, font=font_label).grid(row=0, column=0, padx=(0, 12), pady=10, sticky="e")
    entry_user = tk.Entry(frame, font=(FONT_FAMILY, 11), width=FORM_EMAIL_WIDTH)
    entry_user.grid(row=0, column=1, pady=10, sticky="w")

    tk.Label(frame, text="收件人邮箱:", bg=APP_BG, font=font_label).grid(row=1, column=0, padx=(0, 12), pady=10, sticky="e")
    entry_receiver = tk.Entry(frame, font=(FONT_FAMILY, 11), width=FORM_EMAIL_WIDTH)
    entry_receiver.grid(row=1, column=1, pady=10, sticky="w")

    tk.Label(frame, text="发件人邮箱密码:", bg=APP_BG, font=font_label).grid(row=2, column=0, padx=(0, 12), pady=10, sticky="e")
    entry_password = tk.Entry(
        frame, font=(FONT_FAMILY, 11), width=FORM_EMAIL_WIDTH, show="*"
    )
    entry_password.grid(row=2, column=1, pady=10, sticky="w")

    current_config = load_email_config() or {}
    entry_user.insert(0, current_config.get("EMAIL_USER", ""))
    entry_receiver.insert(0, current_config.get("EMAIL_RECEIVER", ""))
    entry_password.insert(0, current_config.get("EMAIL_PASSWORD", ""))

    def close_popup():
        popup.destroy()
        if temp_root.winfo_exists():
            temp_root.destroy()

    def confirm():
        email_user = entry_user.get().strip()
        email_receiver = entry_receiver.get().strip()
        email_password = entry_password.get().strip()
        if not email_user or not email_receiver or not email_password:
            messagebox.showwarning("提示", "请填写完整信息")
            return
        save_email_config(email_user, email_receiver, email_password)
        messagebox.showinfo("成功", "邮箱配置已保存")
        try:
            update_email_label()
            ensure_scheduler_running()
        except (NameError, tk.TclError):
            pass
        close_popup()

    def disable_email():
        save_email_disabled()
        try:
            update_email_label()
        except (NameError, tk.TclError):
            pass
        close_popup()

    btn_frame = tk.Frame(frame, bg=APP_BG)
    btn_frame.grid(row=3, column=0, columnspan=2, pady=20)

    ttk.Button(btn_frame, text="保存并启用", command=confirm, style="Primary.TButton").pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text="暂不启用邮件", command=disable_email).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text="测试发送", command=test_email).pack(side=tk.LEFT, padx=6)
    popup.protocol(
        "WM_DELETE_WINDOW",
        close_popup if current_config else disable_email
    )
    popup.grab_set()
    popup.wait_window()
#-----------------邮箱配置测试------------------------
def test_email():
    config = load_email_config()
    if not email_reminders_enabled(config):
        messagebox.showwarning("提示", "邮件提醒尚未启用，请先在“邮箱设置”中保存并启用。")
        return
        
    try:
        smtp_server = "smtp.zju.edu.cn"
        smtp_port = 994
        EMAIL_USER = config["EMAIL_USER"]
        EMAIL_RECEIVER = config["EMAIL_RECEIVER"]
        EMAIL_PASSWORD = config["EMAIL_PASSWORD"]
        
        msg = MIMEText("CryoCell Reminder 邮件测试成功！", "plain", "utf-8")
        msg["Subject"] = "CryoCell Reminder 邮件测试"
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_RECEIVER

        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, [EMAIL_RECEIVER], msg.as_string())
        server.quit()

        messagebox.showinfo("成功", "测试邮件发送成功！✅")
        return True
    except Exception as e:
        error_msg = f"测试邮件发送失败！\n错误信息：{e}"
        messagebox.showerror("错误", error_msg)
        log_message(f"测试邮件失败: {e}")
        return False


# ------------------- 数据库初始化 -------------------
def init_db():
    print(f"初始化数据库路径: {DB_PATH}")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cell_records'")
        if not cursor.fetchone():
            print("创建cell_records表")
            cursor.execute("""
                CREATE TABLE cell_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cell_name TEXT NOT NULL,
                    freeze_date TEXT NOT NULL,
                    remind_date TEXT NOT NULL,
                    notified INTEGER DEFAULT 0,
                    box_id INTEGER,
                    position TEXT
                )
            """)
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='freeze_boxes'")
        if not cursor.fetchone():
            print("创建freeze_boxes表")
            cursor.execute("""
                CREATE TABLE freeze_boxes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    box_name TEXT NOT NULL
                )
            """)
        
        conn.commit()
        print("数据库初始化完成")
        return True
    except sqlite3.Error as e:
        print(f"数据库初始化错误: {e}")
        messagebox.showerror("数据库错误", 
            f"无法初始化数据库:\n{e}\n\n"
            f"请检查路径: {DB_PATH}\n"
            "是否有写权限？")
        return False
    finally:
        if conn:
            conn.close()

# ------------------- 添加细胞记录 -------------------
def add_record():
    selected_pos = [[]]  # 保存选择的位置

    def choose_position():
        selected_box_name = box_var.get()
        if selected_box_name == "不指定":
            messagebox.showinfo("提示", "未选择冻存盒")
            return
        box_id = box_dict[selected_box_name]
        pos = open_position_selector(box_id)
        if pos:
            selected_pos[0] = pos
            pos_label.config(text=f"已选位置: {len(selected_pos[0])}个")

    def confirm_add():
        cell_name = entry_name.get().strip()
        if not cell_name:
            messagebox.showwarning("提示", "请输入细胞名称")
            return

        selected_box_name = box_var.get()
        if selected_box_name == "不指定":
            box_id = None
            positions = []
        else:
            box_id = box_dict[selected_box_name]
            positions = selected_pos[0]  # 获取多选位置列表

        # 验证至少选择一个位置（如果指定了冻存盒）
        if selected_box_name != "不指定" and not positions:
            messagebox.showwarning("提示", "请至少选择一个位置")
            return

        freeze_date = datetime.date.today()
    
        try:
            days = int(entry_days.get())
            if days <= 0:
                raise ValueError
        except ValueError:
            days = 14

        remind_date = freeze_date + datetime.timedelta(days=days)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
    
        # 为每个位置插入记录
        for pos in positions:
            cursor.execute("""
                INSERT INTO cell_records 
                (cell_name, freeze_date, remind_date, box_id, position) 
                VALUES (?, ?, ?, ?, ?)
            """, (cell_name, freeze_date.isoformat(), remind_date.isoformat(), box_id, pos))
    
        conn.commit()
        conn.close()

        log_message(f"添加记录：{cell_name} ×{len(positions)}，提醒日期：{remind_date}")
        refresh_table()
        popup.destroy()

    popup = create_hidden_toplevel(root)
    popup.title("添加细胞记录")
    apply_modern_theme(popup)
    fit_window(popup, 480, 390, 380, 330)

    font_label = (FONT_FAMILY, 11)
    font_entry = (FONT_FAMILY, 11)

    form_frame = tk.Frame(popup, padx=24, pady=24, bg=APP_BG)
    form_frame.pack(fill=tk.BOTH, expand=True)
    form_frame.columnconfigure(1, weight=1)

    tk.Label(form_frame, text="细胞名称:", bg=APP_BG, font=font_label).grid(row=0, column=0, padx=(0, 12), sticky="e", pady=10)
    entry_name = tk.Entry(form_frame, font=font_entry, width=FORM_TEXT_WIDTH)
    entry_name.grid(row=0, column=1, pady=10, sticky="w")

    tk.Label(form_frame, text="提醒天数 (默认14):", bg=APP_BG, font=font_label).grid(row=1, column=0, padx=(0, 12), sticky="e", pady=10)
    entry_days = tk.Entry(form_frame, font=font_entry, width=FORM_SHORT_WIDTH)
    entry_days.insert(0, "14")
    entry_days.grid(row=1, column=1, pady=10, sticky="w")

    tk.Label(form_frame, text="冻存盒:", bg=APP_BG, font=font_label).grid(row=2, column=0, padx=(0, 12), sticky="e", pady=10)
    box_var = tk.StringVar()
    boxes = get_boxes()
    box_dict = {"不指定": None}
    for b in boxes:
        box_dict[f"{b[1]} (ID {b[0]})"] = b[0]

    box_menu = ttk.Combobox(
        form_frame, textvariable=box_var, values=list(box_dict.keys()),
        font=(FONT_FAMILY, 11), width=FORM_COMBO_WIDTH, state="readonly"
    )
    box_menu.grid(row=2, column=1, pady=10, sticky="w")
    box_menu.current(0)

    ttk.Button(form_frame, text="选择位置", command=choose_position).grid(row=3, column=0, columnspan=2, pady=10)
    pos_label = tk.Label(form_frame, text="未选择位置", bg=APP_BG, font=(FONT_FAMILY, 10, "italic"), fg=TEXT_SECONDARY)
    pos_label.grid(row=4, column=0, columnspan=2, pady=5)

    ttk.Button(form_frame, text="确认添加", command=confirm_add, style="Primary.TButton").grid(row=5, column=0, columnspan=2, pady=15)

#--------------冻存盒位置选择----------------------
def open_position_selector(box_id):
    selected_pos = set()  # 使用集合存储多选位置
    confirmed = [False]   # 确认状态

    selector = create_hidden_toplevel(root)
    selector.title("选择位置")
    apply_modern_theme(selector)
    fit_window(selector, 780, 650, 620, 480)

    # 添加确认按钮框架
    btn_frame = tk.Frame(selector, bg=APP_BG, pady=10)
    btn_frame.pack(side=tk.BOTTOM, fill=tk.X)

    # 确认按钮
    def on_confirm():
        confirmed[0] = True
        selector.destroy()

    ttk.Button(btn_frame, text="确认选择", command=on_confirm, style="Primary.TButton").pack()

    # 网格框架
    grid_frame = tk.Frame(selector, bg=APP_BG)
    grid_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
    for index in range(9):
        grid_frame.rowconfigure(index, weight=1, uniform="position_rows")
        grid_frame.columnconfigure(index, weight=1, uniform="position_columns")

    # 获取已占用位置
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT position FROM cell_records WHERE box_id = ? AND position IS NOT NULL", (box_id,))
    occupied = {row[0] for row in cursor.fetchall()}
    conn.close()

    # 按钮点击处理
    def toggle_pos(pos, btn):
        if pos in selected_pos:
            selected_pos.remove(pos)
            btn.config(bg=CARD_BG, fg=TEXT_PRIMARY)
        else:
            selected_pos.add(pos)
            btn.config(bg=ACCENT, fg="white")

    # 生成网格按钮
    buttons = {}
    for i, row_label in enumerate("ABCDEFGHI"):
        for j in range(1, 10):
            pos = f"{row_label}{j}"
            btn = tk.Button(grid_frame, text=pos,
                            bg=CARD_BG if pos not in occupied else HEADING_BG,
                            fg=TEXT_PRIMARY if pos not in occupied else TEXT_SECONDARY,
                            activebackground=HOVER_BG, activeforeground=ACCENT_DARK,
                            relief="flat", bd=1, font=(FONT_FAMILY, 10, "bold"),
                            state=tk.NORMAL if pos not in occupied else tk.DISABLED)
            btn.grid(row=i, column=j-1, padx=3, pady=3, sticky="nsew")
            if pos not in occupied:
                btn.configure(command=lambda p=pos, b=btn: toggle_pos(p, b))
            buttons[pos] = btn

    selector.wait_window()
    return list(selected_pos) if confirmed[0] else None

# ------------------- 新建冻存盒 -------------------
def create_box():
    popup = create_hidden_toplevel(root)
    popup.title("新建冻存盒")
    apply_modern_theme(popup)
    fit_window(popup, 400, 220, 320, 180)

    frame = tk.Frame(popup, bg=APP_BG, padx=24, pady=24)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(frame, text="冻存盒名称:", bg=APP_BG, font=(FONT_FAMILY, 11)).pack(pady=(0, 10))
    entry = tk.Entry(frame, font=(FONT_FAMILY, 11), width=FORM_TEXT_WIDTH)
    entry.pack()

    def confirm_create():
        box_name = entry.get().strip()
        if not box_name:
            messagebox.showwarning("警告", "请输入冻存盒名称")
            return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO freeze_boxes (box_name) VALUES (?)", (box_name,))
        conn.commit()
        conn.close()
        log_message(f"新建冻存盒：{box_name}")
        messagebox.showinfo("成功", f"冻存盒 '{box_name}' 创建成功！")
        popup.destroy()

    ttk.Button(frame, text="确认创建", command=confirm_create, style="Primary.TButton").pack(pady=18)


# ------------------- 导出盒子布局到Excel -------------------
def export_box():
    boxes = get_boxes()
    if not boxes:
        messagebox.showwarning("提示", "当前没有冻存盒")
        return

    box_dict = {f"{b[1]} (ID {b[0]})": b[0] for b in boxes}
    popup = create_hidden_toplevel(root)
    popup.title("选择盒子导出")
    apply_modern_theme(popup)
    fit_window(popup, 440, 250, 340, 200)

    frame = tk.Frame(popup, bg=APP_BG, padx=24, pady=24)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(frame, text="选择冻存盒:", bg=APP_BG, font=(FONT_FAMILY, 11)).pack(pady=10)
    box_var = tk.StringVar()
    combo = ttk.Combobox(
        frame, values=list(box_dict.keys()), textvariable=box_var,
        font=(FONT_FAMILY, 11), width=FORM_COMBO_WIDTH, state="readonly"
    )
    combo.pack()

    def do_export():
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

        selected = box_var.get()
        if not selected:
            return
        box_id = box_dict[selected]

        conn = sqlite3.connect(DB_PATH)
        records = conn.execute(
            """
            SELECT position, cell_name
            FROM cell_records
            WHERE box_id = ? AND position IS NOT NULL
            """,
            (box_id,)
        ).fetchall()
        conn.close()

        box_name_clean = selected.split(" (ID")[0].replace(" ", "_")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = resource_path(f"{box_name_clean}_{timestamp}.xlsx")

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "冻存盒布局"
        header_fill = PatternFill("solid", fgColor="DDE8F5")
        for column in range(1, 10):
            cell = sheet.cell(1, column + 1, column)
            cell.font = Font(name="Microsoft YaHei", bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        for row_index, row_name in enumerate("ABCDEFGHI", 2):
            cell = sheet.cell(row_index, 1, row_name)
            cell.font = Font(name="Microsoft YaHei", bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        for position, cell_name in records:
            match = re.fullmatch(r"([A-Ia-i])([1-9])", position or "")
            if not match:
                continue
            row_index = ord(match.group(1).upper()) - ord("A") + 2
            column_index = int(match.group(2)) + 1
            cell = sheet.cell(row_index, column_index, cell_name)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        sheet.column_dimensions["A"].width = 6
        for column_letter in "BCDEFGHIJ":
            sheet.column_dimensions[column_letter].width = 18
        workbook.save(filename)
        workbook.close()
        messagebox.showinfo("导出成功", f"布局已导出到 {filename}")
        popup.destroy()

    ttk.Button(frame, text="导出", command=do_export, style="Primary.TButton").pack(pady=20)


# ------------------- 导入外部冻存盒 -------------------
def export_import_template(parent=None):
    """导出带 A-I / 1-9 标题的标准冻存盒导入模板。"""
    dialog_parent = parent or root
    filename = filedialog.asksaveasfilename(
        parent=dialog_parent,
        title="保存标准冻存盒模板",
        initialdir=get_app_dir(),
        initialfile="冻存盒9x9导入模板.xlsx",
        defaultextension=".xlsx",
        filetypes=[("Excel 工作簿", "*.xlsx")]
    )
    if not filename:
        return
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "冻存盒"
        thin = Side(style="thin", color="A1A1A6")
        header_fill = PatternFill("solid", fgColor="DCEBFF")
        for column in range(1, 10):
            cell = sheet.cell(1, column + 1, column)
            cell.font = Font(name="Microsoft YaHei", bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        for row_index, row_name in enumerate("ABCDEFGHI", 2):
            cell = sheet.cell(row_index, 1, row_name)
            cell.font = Font(name="Microsoft YaHei", bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
            for column in range(2, 11):
                data_cell = sheet.cell(row_index, column)
                data_cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
                data_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        sheet.column_dimensions["A"].width = 6
        for column in range(2, 11):
            sheet.column_dimensions[chr(64 + column)].width = 18
        for row in range(2, 11):
            sheet.row_dimensions[row].height = 32
        sheet.freeze_panes = "B2"
        workbook.save(filename)
        messagebox.showinfo("模板已保存", f"标准9×9模板已保存到：\n{filename}", parent=dialog_parent)
    except Exception as e:
        messagebox.showerror("导出失败", f"无法生成模板：\n{e}", parent=dialog_parent)


def import_boxes():
    class ImportBoxesWindow:
        CELL_WIDTH = 92
        CELL_HEIGHT = 28
        MAX_PREVIEW_ROWS = 300
        MAX_PREVIEW_COLUMNS = 40

        def __init__(self, parent):
            self.window = create_hidden_toplevel(parent)
            self.window.title("导入冻存盒")
            apply_modern_theme(self.window)
            fit_window(self.window, 1180, 760, 820, 580)
            self.window.transient(parent)

            self.sheet_sources = {}
            self.current_sheet_key = None
            self.selected_top_left = None
            self.staged_boxes = []
            self.preview_entries = {}
            self.canvas_start_row = 1
            self.canvas_start_column = 1
            self.canvas_rows = 0
            self.canvas_columns = 0

            self.build_interface()
            self.window.bind("<<ThemeChanged>>", self.on_theme_changed)
            self.window.protocol("WM_DELETE_WINDOW", self.close)

        def on_theme_changed(self, event=None):
            """Canvas 图元不是普通控件，切换主题后需要重新绘制。"""
            self.sheet_canvas.configure(bg=CARD_BG)
            self.render_sheet()

        def close(self):
            """及时释放大型工作表预览和待导入数据，适合后台长期运行。"""
            self.sheet_sources.clear()
            self.staged_boxes.clear()
            self.preview_entries.clear()
            self.window.destroy()

        def build_interface(self):
            title_frame = tk.Frame(self.window, bg=APP_BG)
            title_frame.pack(fill=tk.X, padx=16, pady=(14, 8))
            tk.Label(
                title_frame, text="导入外部冻存盒", bg=APP_BG, fg=TEXT_PRIMARY,
                font=(FONT_FAMILY, 16, "bold")
            ).pack(side=tk.LEFT)
            tk.Label(
                title_frame, text="在左侧点击实际细胞区左上角，右侧将预览固定9×9",
                bg=APP_BG, fg=TEXT_SECONDARY, font=(FONT_FAMILY, 9)
            ).pack(side=tk.RIGHT)

            source_frame = tk.Frame(
                self.window, bg=CARD_BG, padx=10, pady=8,
                highlightthickness=1, highlightbackground=BORDER_COLOR
            )
            source_frame.pack(fill=tk.X, padx=16, pady=(0, 8))
            ttk.Button(source_frame, text="选择 Excel 文件", command=self.choose_excel_files).pack(side=tk.LEFT, padx=3)
            ttk.Button(source_frame, text="粘贴 Excel 9×9", command=self.paste_from_clipboard).pack(side=tk.LEFT, padx=3)
            ttk.Button(
                source_frame, text="导出标准模板",
                command=lambda: export_import_template(self.window)
            ).pack(side=tk.LEFT, padx=3)
            self.source_status = tk.Label(
                source_frame, text="尚未载入 Excel", bg=CARD_BG,
                fg=TEXT_SECONDARY, font=(FONT_FAMILY, 9)
            )
            self.source_status.pack(side=tk.RIGHT, padx=6)

            workspace = tk.PanedWindow(
                self.window, orient=tk.HORIZONTAL, sashwidth=5,
                bg=APP_BG, bd=0, relief="flat"
            )
            workspace.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

            left = tk.Frame(workspace, bg=APP_BG)
            right = tk.Frame(workspace, bg=APP_BG)
            workspace.add(left, minsize=420, stretch="always")
            workspace.add(right, minsize=390, stretch="always")

            sheet_bar = tk.Frame(left, bg=APP_BG)
            sheet_bar.pack(fill=tk.X, pady=(0, 5))
            tk.Label(sheet_bar, text="工作表", bg=APP_BG, fg=TEXT_SECONDARY).pack(side=tk.LEFT)
            self.sheet_var = tk.StringVar()
            self.sheet_combo = ttk.Combobox(
                sheet_bar, textvariable=self.sheet_var, state="readonly", width=42
            )
            self.sheet_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
            self.sheet_combo.bind("<<ComboboxSelected>>", self.on_sheet_changed)

            canvas_frame = tk.Frame(
                left, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER_COLOR
            )
            canvas_frame.pack(fill=tk.BOTH, expand=True)
            self.sheet_canvas = tk.Canvas(
                canvas_frame, bg=CARD_BG, highlightthickness=0,
                xscrollincrement=self.CELL_WIDTH, yscrollincrement=self.CELL_HEIGHT
            )
            canvas_x = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.sheet_canvas.xview)
            canvas_y = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.sheet_canvas.yview)
            self.sheet_canvas.configure(xscrollcommand=canvas_x.set, yscrollcommand=canvas_y.set)
            self.sheet_canvas.grid(row=0, column=0, sticky="nsew")
            canvas_y.grid(row=0, column=1, sticky="ns")
            canvas_x.grid(row=1, column=0, sticky="ew")
            canvas_frame.rowconfigure(0, weight=1)
            canvas_frame.columnconfigure(0, weight=1)
            self.sheet_canvas.bind("<Button-1>", self.on_canvas_click)

            region_bar = tk.Frame(right, bg=APP_BG)
            region_bar.pack(fill=tk.X, pady=(0, 5))
            tk.Label(region_bar, text="细胞区左上角", bg=APP_BG, fg=TEXT_SECONDARY).pack(side=tk.LEFT)
            self.top_left_var = tk.StringVar(value="")
            top_left_entry = tk.Entry(
                region_bar, textvariable=self.top_left_var, width=9,
                bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                relief="flat", highlightthickness=1,
                highlightbackground=BORDER_COLOR, highlightcolor=ACCENT
            )
            top_left_entry.pack(side=tk.LEFT, padx=6, ipady=4)
            ttk.Button(region_bar, text="按坐标载入9×9", command=self.load_manual_region).pack(side=tk.LEFT)

            preview_card = tk.Frame(
                right, bg=APP_BG, highlightthickness=1, highlightbackground=BORDER_COLOR
            )
            preview_card.pack(fill=tk.BOTH, expand=True)
            for index in range(9):
                preview_card.rowconfigure(index, weight=1, uniform="import_rows")
                preview_card.columnconfigure(index, weight=1, uniform="import_columns")
            for row_index, row_name in enumerate("ABCDEFGHI"):
                for column_index in range(1, 10):
                    position = f"{row_name}{column_index}"
                    entry = tk.Entry(
                        preview_card, justify="center", font=(FONT_FAMILY, 8),
                        bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                        relief="flat", bd=0, highlightthickness=1,
                        highlightbackground=BORDER_COLOR, highlightcolor=ACCENT
                    )
                    entry.grid(row=row_index, column=column_index - 1, padx=1, pady=1, sticky="nsew")
                    self.preview_entries[position] = entry

            name_frame = tk.Frame(right, bg=APP_BG)
            name_frame.pack(fill=tk.X, pady=7)
            tk.Label(name_frame, text="冻存盒名称", bg=APP_BG, fg=TEXT_SECONDARY).pack(side=tk.LEFT)
            self.box_name_var = tk.StringVar()
            self.box_name_entry = tk.Entry(
                name_frame, textvariable=self.box_name_var,
                width=FORM_TEXT_WIDTH,
                bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                relief="flat", highlightthickness=1,
                highlightbackground=BORDER_COLOR, highlightcolor=ACCENT
            )
            self.box_name_entry.pack(side=tk.LEFT, padx=6, ipady=4)
            ttk.Button(
                name_frame, text="确认并加入", command=self.add_current_preview,
                style="Primary.TButton"
            ).pack(side=tk.LEFT)

            staging = tk.Frame(self.window, bg=APP_BG)
            staging.pack(fill=tk.X, padx=16, pady=6)
            columns = ("name", "source", "top_left", "count")
            self.stage_tree = ttk.Treeview(staging, columns=columns, show="headings", height=4)
            self.stage_tree.heading("name", text="冻存盒名称")
            self.stage_tree.heading("source", text="来源")
            self.stage_tree.heading("top_left", text="区域")
            self.stage_tree.heading("count", text="细胞数")
            self.stage_tree.column("name", width=220)
            self.stage_tree.column("source", width=420)
            self.stage_tree.column("top_left", width=100, anchor="center")
            self.stage_tree.column("count", width=80, anchor="center")
            self.stage_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
            stage_scroll = ttk.Scrollbar(staging, orient=tk.VERTICAL, command=self.stage_tree.yview)
            stage_scroll.pack(side=tk.LEFT, fill=tk.Y)
            self.stage_tree.configure(yscrollcommand=stage_scroll.set)
            stage_buttons = tk.Frame(staging, bg=APP_BG)
            stage_buttons.pack(side=tk.LEFT, padx=(8, 0))
            ttk.Button(stage_buttons, text="查看", command=self.view_staged_box).pack(fill=tk.X, pady=2)
            ttk.Button(stage_buttons, text="更新所选", command=self.update_staged_box).pack(fill=tk.X, pady=2)
            ttk.Button(stage_buttons, text="移除", command=self.remove_staged_box).pack(fill=tk.X, pady=2)
            self.stage_tree.bind("<Double-1>", lambda event: self.view_staged_box())

            footer = tk.Frame(
                self.window, bg=CARD_BG, padx=12, pady=9,
                highlightthickness=1, highlightbackground=BORDER_COLOR
            )
            footer.pack(fill=tk.X, padx=16, pady=(4, 14))
            tk.Label(footer, text="冻存日期", bg=CARD_BG, fg=TEXT_SECONDARY).pack(side=tk.LEFT)
            self.freeze_date_var = tk.StringVar(value=datetime.date.today().isoformat())
            tk.Entry(
                footer, textvariable=self.freeze_date_var, width=12,
                bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                relief="flat", highlightthickness=1,
                highlightbackground=BORDER_COLOR, highlightcolor=ACCENT
            ).pack(side=tk.LEFT, padx=6, ipady=4)
            tk.Label(footer, text="提醒天数", bg=CARD_BG, fg=TEXT_SECONDARY).pack(side=tk.LEFT, padx=(10, 0))
            self.remind_days_var = tk.StringVar(value="14")
            tk.Entry(
                footer, textvariable=self.remind_days_var, width=7,
                bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                relief="flat", highlightthickness=1,
                highlightbackground=BORDER_COLOR, highlightcolor=ACCENT
            ).pack(side=tk.LEFT, padx=6, ipady=4)
            self.import_button = ttk.Button(
                footer, text="导入已确认冻存盒", command=self.commit_import,
                style="Primary.TButton"
            )
            self.import_button.pack(side=tk.RIGHT)

        @staticmethod
        def display_value(value):
            if value is None:
                return ""
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value).strip()

        def read_workbook(self, path):
            suffix = os.path.splitext(path)[1].lower()
            sheets = {}
            if suffix in (".xlsx", ".xlsm", ".xltx", ".xltm"):
                from openpyxl import load_workbook
                workbook = load_workbook(path, data_only=True, read_only=True)
                try:
                    for worksheet in workbook.worksheets:
                        used_rows = max(1, worksheet.max_row - worksheet.min_row + 1)
                        used_columns = max(1, worksheet.max_column - worksheet.min_column + 1)
                        if used_rows * used_columns > 500000:
                            raise ValueError(
                                f"工作表“{worksheet.title}”使用区域过大"
                                f"（{used_rows}×{used_columns}），请先删除无用空白格式后再导入"
                            )
                        values = {}
                        for row in worksheet.iter_rows(
                            min_row=worksheet.min_row, max_row=worksheet.max_row,
                            min_col=worksheet.min_column, max_col=worksheet.max_column
                        ):
                            for cell in row:
                                value = self.display_value(cell.value)
                                if value:
                                    values[(cell.row, cell.column)] = value
                        sheets[worksheet.title] = {
                            "values": values,
                            "min_row": max(1, worksheet.min_row), "max_row": max(1, worksheet.max_row),
                            "min_col": max(1, worksheet.min_column), "max_col": max(1, worksheet.max_column),
                        }
                finally:
                    workbook.close()
            elif suffix == ".xls":
                import pandas as pd

                excel_file = pd.ExcelFile(path)
                for sheet_name in excel_file.sheet_names:
                    frame = pd.read_excel(path, sheet_name=sheet_name, header=None, dtype=object)
                    values = {}
                    for row_index in range(frame.shape[0]):
                        for column_index in range(frame.shape[1]):
                            value = frame.iat[row_index, column_index]
                            if pd.notna(value):
                                values[(row_index + 1, column_index + 1)] = self.display_value(value)
                    sheets[sheet_name] = {
                        "values": values,
                        "min_row": 1, "max_row": max(1, frame.shape[0]),
                        "min_col": 1, "max_col": max(1, frame.shape[1]),
                    }
            else:
                raise ValueError("仅支持 .xlsx、.xlsm 和 .xls 文件")
            return sheets

        def choose_excel_files(self):
            paths = filedialog.askopenfilenames(
                parent=self.window,
                title="选择一个或多个冻存盒 Excel",
                filetypes=[
                    ("Excel 文件", "*.xlsx *.xlsm *.xls"),
                    ("所有文件", "*.*")
                ]
            )
            if not paths:
                return
            failures = []
            added = 0
            for path in paths:
                try:
                    sheets = self.read_workbook(path)
                    for sheet_name, data in sheets.items():
                        key = f"{path}::{sheet_name}"
                        self.sheet_sources[key] = {
                            "path": path, "sheet_name": sheet_name, "data": data
                        }
                        added += 1
                except Exception as e:
                    failures.append(f"{os.path.basename(path)}：{e}")
            self.refresh_sheet_list()
            self.source_status.config(text=f"已载入 {len(paths)} 个文件 / {added} 个工作表")
            if failures:
                messagebox.showwarning(
                    "部分文件未载入", "\n".join(failures[:8]), parent=self.window
                )
            if self.sheet_sources:
                self.source_status.config(text="工作表已载入，请点击左侧细胞区的左上角")

        def refresh_sheet_list(self):
            labels = []
            self.sheet_label_to_key = {}
            for key, source in self.sheet_sources.items():
                label = f"{os.path.basename(source['path'])} · {source['sheet_name']}"
                if label in self.sheet_label_to_key:
                    label = f"{label} ({len(labels) + 1})"
                labels.append(label)
                self.sheet_label_to_key[label] = key
            self.sheet_combo["values"] = labels
            if labels:
                self.sheet_combo.current(0)
                self.on_sheet_changed()

        def on_sheet_changed(self, event=None):
            self.current_sheet_key = self.sheet_label_to_key.get(self.sheet_var.get())
            if not self.current_sheet_key:
                return
            source = self.sheet_sources[self.current_sheet_key]
            data = source["data"]
            self.selected_top_left = None
            self.top_left_var.set("")
            suggested = os.path.splitext(os.path.basename(source["path"]))[0]
            if source["sheet_name"].lower() not in ("sheet", "sheet1", "工作表1"):
                suggested = source["sheet_name"]
            self.box_name_var.set(suggested)
            self.render_sheet()
            self.clear_preview()
            self.source_status.config(text="请点击左侧实际细胞区的左上角")

        @staticmethod
        def coordinate_label(row, column):
            from openpyxl.utils import get_column_letter
            return f"{get_column_letter(column)}{row}"

        def parse_coordinate(self, coordinate):
            from openpyxl.utils.cell import coordinate_to_tuple
            return coordinate_to_tuple(coordinate.strip().upper())

        def render_sheet(self):
            self.sheet_canvas.delete("all")
            if not self.current_sheet_key:
                return
            data = self.sheet_sources[self.current_sheet_key]["data"]
            self.canvas_start_row = data["min_row"]
            self.canvas_start_column = data["min_col"]
            self.canvas_rows = min(
                self.MAX_PREVIEW_ROWS,
                max(9, data["max_row"] - self.canvas_start_row + 1)
            )
            self.canvas_columns = min(
                self.MAX_PREVIEW_COLUMNS,
                max(9, data["max_col"] - self.canvas_start_column + 1)
            )
            header_width = 46
            header_height = 28
            for display_column in range(self.canvas_columns):
                actual_column = self.canvas_start_column + display_column
                x1 = header_width + display_column * self.CELL_WIDTH
                self.sheet_canvas.create_rectangle(
                    x1, 0, x1 + self.CELL_WIDTH, header_height,
                    fill=HEADING_BG, outline=BORDER_COLOR
                )
                self.sheet_canvas.create_text(
                    x1 + self.CELL_WIDTH / 2, header_height / 2,
                    text=self.coordinate_label(1, actual_column)[:-1],
                    fill=TEXT_PRIMARY, font=(FONT_FAMILY, 9, "bold")
                )
            for display_row in range(self.canvas_rows):
                actual_row = self.canvas_start_row + display_row
                y1 = header_height + display_row * self.CELL_HEIGHT
                self.sheet_canvas.create_rectangle(
                    0, y1, header_width, y1 + self.CELL_HEIGHT,
                    fill=HEADING_BG, outline=BORDER_COLOR
                )
                self.sheet_canvas.create_text(
                    header_width / 2, y1 + self.CELL_HEIGHT / 2,
                    text=str(actual_row), fill=TEXT_PRIMARY,
                    font=(FONT_FAMILY, 9, "bold")
                )
                for display_column in range(self.canvas_columns):
                    actual_column = self.canvas_start_column + display_column
                    x1 = header_width + display_column * self.CELL_WIDTH
                    value = data["values"].get((actual_row, actual_column), "")
                    shown = value if len(value) <= 14 else value[:12] + "…"
                    self.sheet_canvas.create_rectangle(
                        x1, y1, x1 + self.CELL_WIDTH, y1 + self.CELL_HEIGHT,
                        fill=CARD_BG, outline=BORDER_COLOR
                    )
                    self.sheet_canvas.create_text(
                        x1 + 4, y1 + self.CELL_HEIGHT / 2,
                        text=shown, anchor="w", fill=TEXT_PRIMARY,
                        font=(FONT_FAMILY, 8)
                    )
            total_width = header_width + self.canvas_columns * self.CELL_WIDTH
            total_height = header_height + self.canvas_rows * self.CELL_HEIGHT
            self.sheet_canvas.configure(scrollregion=(0, 0, total_width, total_height))
            self.draw_region_highlight()

        def draw_region_highlight(self):
            self.sheet_canvas.delete("region_highlight")
            if self.selected_top_left is None:
                return
            row, column = self.selected_top_left
            display_row = row - self.canvas_start_row
            display_column = column - self.canvas_start_column
            if not (0 <= display_row < self.canvas_rows and 0 <= display_column < self.canvas_columns):
                return
            x1 = 46 + display_column * self.CELL_WIDTH
            y1 = 28 + display_row * self.CELL_HEIGHT
            self.sheet_canvas.create_rectangle(
                x1, y1, x1 + 9 * self.CELL_WIDTH, y1 + 9 * self.CELL_HEIGHT,
                outline=ACCENT, width=3, tags="region_highlight"
            )

        def on_canvas_click(self, event):
            x = self.sheet_canvas.canvasx(event.x)
            y = self.sheet_canvas.canvasy(event.y)
            if x < 46 or y < 28:
                return
            column = self.canvas_start_column + int((x - 46) // self.CELL_WIDTH)
            row = self.canvas_start_row + int((y - 28) // self.CELL_HEIGHT)
            self.selected_top_left = (row, column)
            coordinate = self.coordinate_label(row, column)
            self.top_left_var.set(coordinate)
            cells = self.extract_region(
                self.sheet_sources[self.current_sheet_key]["data"], row, column
            )
            self.load_region(row, column, cells)
            self.draw_region_highlight()
            self.source_status.config(
                text=f"已选择 {coordinate} 起始的9×9区域，共 {self.occupied_count(cells)} 个细胞"
            )

        def load_manual_region(self):
            if not self.current_sheet_key:
                messagebox.showwarning("未选择工作表", "请先载入并选择 Excel 工作表。", parent=self.window)
                return
            try:
                row, column = self.parse_coordinate(self.top_left_var.get())
            except Exception:
                messagebox.showwarning("位置错误", "请输入类似 A1、B3 的 Excel 单元格地址。", parent=self.window)
                return
            self.selected_top_left = (row, column)
            cells = self.extract_region(
                self.sheet_sources[self.current_sheet_key]["data"], row, column
            )
            self.load_region(row, column, cells)
            self.draw_region_highlight()
            self.source_status.config(
                text=f"已载入 {self.coordinate_label(row, column)} 起始的9×9区域，"
                f"共 {self.occupied_count(cells)} 个细胞"
            )

        def extract_region(self, data, top_row, left_column):
            return [
                [
                    data["values"].get(
                        (top_row + row_offset, left_column + column_offset), ""
                    )
                    for column_offset in range(9)
                ]
                for row_offset in range(9)
            ]

        def clear_preview(self):
            for entry in self.preview_entries.values():
                entry.delete(0, tk.END)

        def load_region(self, row, column, cells=None):
            if cells is None:
                data = self.sheet_sources[self.current_sheet_key]["data"]
                cells = self.extract_region(data, row, column)
            for row_index, row_name in enumerate("ABCDEFGHI"):
                for column_index in range(1, 10):
                    entry = self.preview_entries[f"{row_name}{column_index}"]
                    entry.delete(0, tk.END)
                    value = cells[row_index][column_index - 1]
                    if value:
                        entry.insert(0, value)

        def current_preview_cells(self):
            cells = []
            for row_name in "ABCDEFGHI":
                row_values = []
                for column_index in range(1, 10):
                    value = self.preview_entries[f"{row_name}{column_index}"].get().strip()
                    row_values.append(value)
                cells.append(row_values)
            return cells

        @staticmethod
        def occupied_count(cells):
            return sum(1 for row in cells for value in row if str(value).strip())

        def add_current_preview(self):
            if self.current_sheet_key and self.selected_top_left is None:
                messagebox.showwarning(
                    "尚未选择区域",
                    "请先在左侧点击实际细胞区的左上角，再确认右侧9×9预览。",
                    parent=self.window
                )
                return
            name = self.box_name_var.get().strip()
            if not name:
                messagebox.showwarning("缺少名称", "请先填写冻存盒名称。", parent=self.window)
                return
            cells = self.current_preview_cells()
            if not self.occupied_count(cells):
                if not messagebox.askyesno(
                    "空冻存盒", "当前9×9区域没有细胞，仍要加入待导入列表吗？",
                    parent=self.window
                ):
                    return
            source_text = "剪贴板"
            top_left = "A1"
            if self.current_sheet_key:
                source = self.sheet_sources[self.current_sheet_key]
                source_text = f"{os.path.basename(source['path'])} · {source['sheet_name']}"
                top_left = self.top_left_var.get().upper()
            self.add_staged_box(name, cells, source_text, top_left)

        def add_staged_box(self, name, cells, source_text, top_left):
            existing_names = {item["name"].casefold() for item in self.staged_boxes}
            if name.casefold() in existing_names:
                messagebox.showwarning("名称重复", f"待导入列表中已经存在“{name}”。", parent=self.window)
                return False
            item = {
                "name": name, "cells": [row[:] for row in cells],
                "source": source_text, "top_left": top_left
            }
            self.staged_boxes.append(item)
            self.stage_tree.insert(
                "", tk.END, iid=str(len(self.staged_boxes) - 1),
                values=(name, source_text, top_left, self.occupied_count(cells))
            )
            return True

        def unique_stage_name(self, base_name):
            existing = {item["name"].casefold() for item in self.staged_boxes}
            if base_name.casefold() not in existing:
                return base_name
            suffix = 2
            while f"{base_name}-{suffix}".casefold() in existing:
                suffix += 1
            return f"{base_name}-{suffix}"

        def rebuild_stage_tree(self):
            for item in self.stage_tree.get_children():
                self.stage_tree.delete(item)
            for index, staged in enumerate(self.staged_boxes):
                self.stage_tree.insert(
                    "", tk.END, iid=str(index),
                    values=(
                        staged["name"], staged["source"], staged["top_left"],
                        self.occupied_count(staged["cells"])
                    )
                )

        def view_staged_box(self):
            selected = self.stage_tree.selection()
            if not selected:
                return
            staged = self.staged_boxes[int(selected[0])]
            self.box_name_var.set(staged["name"])
            self.load_region(1, 1, staged["cells"])

        def update_staged_box(self):
            selected = self.stage_tree.selection()
            if len(selected) != 1:
                messagebox.showwarning("请选择一项", "请先选择一个待导入冻存盒。", parent=self.window)
                return
            index = int(selected[0])
            name = self.box_name_var.get().strip()
            if not name:
                messagebox.showwarning("缺少名称", "冻存盒名称不能为空。", parent=self.window)
                return
            duplicate = any(
                other_index != index and item["name"].casefold() == name.casefold()
                for other_index, item in enumerate(self.staged_boxes)
            )
            if duplicate:
                messagebox.showwarning("名称重复", f"待导入列表中已经存在“{name}”。", parent=self.window)
                return
            self.staged_boxes[index]["name"] = name
            self.staged_boxes[index]["cells"] = self.current_preview_cells()
            self.rebuild_stage_tree()
            self.stage_tree.selection_set(str(index))

        def remove_staged_box(self):
            selected = self.stage_tree.selection()
            if not selected:
                return
            indexes = sorted((int(item) for item in selected), reverse=True)
            for index in indexes:
                self.staged_boxes.pop(index)
            self.rebuild_stage_tree()

        def paste_from_clipboard(self):
            try:
                text = self.window.clipboard_get()
            except tk.TclError:
                messagebox.showwarning("剪贴板为空", "请先在 Excel 中复制9×9区域。", parent=self.window)
                return
            normalized = text.replace("\r\n", "\n").replace("\r", "\n")
            rows = normalized.split("\n")
            if rows and rows[-1] == "":
                rows.pop()
            parsed = [row.split("\t") for row in rows]
            if len(parsed) > 9 or any(len(row) > 9 for row in parsed):
                messagebox.showwarning(
                    "区域过大",
                    f"剪贴板区域为 {len(parsed)} 行 × {max((len(row) for row in parsed), default=0)} 列，"
                    "请复制不超过9×9的区域。",
                    parent=self.window
                )
                return
            cells = [["" for _ in range(9)] for _ in range(9)]
            for row_index, row_values in enumerate(parsed[:9]):
                for column_index, value in enumerate(row_values[:9]):
                    cells[row_index][column_index] = value.strip()
            self.current_sheet_key = None
            self.selected_top_left = (1, 1)
            self.sheet_var.set("")
            self.top_left_var.set("A1")
            self.load_region(1, 1, cells)
            self.box_name_var.set("")
            self.box_name_entry.focus_set()
            self.source_status.config(
                text=f"已粘贴 {len(parsed)} 行 × {max((len(row) for row in parsed), default=0)} 列"
            )

        def commit_import(self):
            if not self.staged_boxes:
                messagebox.showwarning("没有待导入内容", "请先加入至少一个冻存盒。", parent=self.window)
                return
            try:
                freeze_date = datetime.datetime.strptime(
                    self.freeze_date_var.get().strip(), "%Y-%m-%d"
                ).date()
                remind_days = int(self.remind_days_var.get().strip())
                if remind_days < 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning(
                    "日期设置错误", "冻存日期应为 YYYY-MM-DD，提醒天数应为非负整数。",
                    parent=self.window
                )
                return

            names = [item["name"].strip() for item in self.staged_boxes]
            if any(not name for name in names) or len({name.casefold() for name in names}) != len(names):
                messagebox.showwarning("名称错误", "冻存盒名称不能为空且不能重复。", parent=self.window)
                return
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT box_name FROM freeze_boxes")
            existing = {row[0].casefold() for row in cursor.fetchall()}
            conflicts = [name for name in names if name.casefold() in existing]
            if conflicts:
                conn.close()
                messagebox.showwarning(
                    "冻存盒名称已存在",
                    "为避免覆盖现有数据，请修改以下名称后重新加入：\n" + "\n".join(conflicts),
                    parent=self.window
                )
                return

            import shutil
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_path = os.path.join(get_app_dir(), f"import_backup_{timestamp}.db")
            try:
                shutil.copy2(DB_PATH, backup_path)
            except OSError as e:
                conn.close()
                messagebox.showerror("备份失败", f"导入已取消，无法备份数据库：\n{e}", parent=self.window)
                return

            remind_date = freeze_date + datetime.timedelta(days=remind_days)
            total_cells = 0
            try:
                cursor.execute("BEGIN")
                for staged in self.staged_boxes:
                    cursor.execute("INSERT INTO freeze_boxes (box_name) VALUES (?)", (staged["name"],))
                    box_id = cursor.lastrowid
                    for row_index, row_name in enumerate("ABCDEFGHI"):
                        for column_index in range(1, 10):
                            cell_name = str(staged["cells"][row_index][column_index - 1]).strip()
                            if not cell_name:
                                continue
                            position = f"{row_name}{column_index}"
                            cursor.execute(
                                """
                                INSERT INTO cell_records
                                (cell_name, freeze_date, remind_date, box_id, position)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (
                                    cell_name, freeze_date.isoformat(), remind_date.isoformat(),
                                    box_id, position
                                )
                            )
                            total_cells += 1
                conn.commit()
            except Exception as e:
                conn.rollback()
                conn.close()
                messagebox.showerror(
                    "导入失败", f"数据未写入，数据库已回滚：\n{e}", parent=self.window
                )
                return
            conn.close()
            log_message(
                f"导入冻存盒：{len(self.staged_boxes)}个盒，{total_cells}个细胞；备份：{backup_path}"
            )
            try:
                refresh_table()
            except Exception:
                pass
            messagebox.showinfo(
                "导入成功",
                f"已导入 {len(self.staged_boxes)} 个冻存盒、{total_cells} 个细胞。\n\n"
                f"导入前备份：\n{backup_path}",
                parent=self.window
            )
            self.window.destroy()

    return ImportBoxesWindow(root)


# ------------------- 刷新主表格-修改版------------
def refresh_table():
    try:
        for row in table.get_children():
            table.delete(row)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.id,
                c.cell_name, 
                c.freeze_date,
                c.remind_date,
                c.notified,
                b.box_name,
                c.position
            FROM cell_records c
            LEFT JOIN freeze_boxes b ON c.box_id = b.id
        """)
        records = cursor.fetchall()
        conn.close()

        columns = ("细胞名称", "添加日期", "提醒日期", "状态", "冻存盒", "位置", "hidden_id")
        table.configure(columns=columns)
        table["displaycolumns"] = columns[:-1]

        for col in columns[:-1]:
            table.heading(col, text=col)
            table.column(col, width=120 if col != "细胞名称" else 200)

        query = search_var.get().lower()
        count = 0
        for r in records:
            status = "已提醒" if r[4] else "待提醒"
            values = (
                r[1],  # 细胞名称
                r[2],  # 添加日期
                r[3],  # 提醒日期
                status,
                r[5] or "未分配",  # 冻存盒
                r[6] or "-",  # 位置
                r[0]   # hidden_id
            )
            
            # 扩展搜索范围
            search_text = f"{r[1]}{r[2]}{r[5]}{r[6]}".lower()
            if not query or query in search_text:
                table.insert("", tk.END, values=values)
                count += 1

        cell_count_label.config(text=f"当前细胞数量：{count}")
        
    except sqlite3.Error as e:
        messagebox.showerror("数据库错误", f"无法读取数据库:\n{e}")
        log_message(f"数据库错误: {e}")

# ------------------- 导出全部细胞记录到Excel -------------------
def export_to_excel():
    from openpyxl import Workbook

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            c.cell_name,
            c.freeze_date,
            c.remind_date,
            b.box_name,
            c.position,
            CASE c.notified WHEN 1 THEN '已提醒' ELSE '待提醒' END
        FROM cell_records c
        LEFT JOIN freeze_boxes b ON c.box_id = b.id
    """)
    rows = cursor.fetchall()
    conn.close()
    
    filename = resource_path("cell_freeze_records.xlsx")
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("细胞记录")
    sheet.append(["细胞名称", "添加日期", "提醒日期", "冻存盒", "位置", "状态"])
    for row in rows:
        sheet.append(list(row))
    workbook.save(filename)
    workbook.close()
    messagebox.showinfo("导出成功", "记录已成功导出为 'cell_freeze_records.xlsx'")
    
# ------------------ 日志记录 ------------------
def log_message(message):
    log_file = resource_path("reminder_log.txt")
    with open(log_file, "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        f.write(f"{timestamp} {message}\n")

# ------------------ 邮件发送 ------------------
def send_reminders(show_result=False):
    """发送一封到期摘要；仅在发送成功后批量标记记录，避免重复与邮件轰炸。"""
    if not reminder_send_lock.acquire(blocking=False):
        if show_result:
            messagebox.showwarning("提醒检查中", "另一项提醒检查正在进行，请稍后再试。")
        return False

    conn = None
    server = None
    try:
        config = load_email_config()
        if not email_reminders_enabled(config):
            log_message("邮件提醒未启用，跳过检查")
            if show_result:
                messagebox.showwarning("邮件提醒未启用", "如需邮件提醒，请先在“邮箱设置”中保存并启用。")
            return True

        email_user = config["EMAIL_USER"]
        email_receiver = config["EMAIL_RECEIVER"]
        email_password = config["EMAIL_PASSWORD"]
        today_date = datetime.date.today()
        today = today_date.isoformat()
        log_message(f"检查提醒: {today}")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, cell_name, freeze_date, remind_date
            FROM cell_records
            WHERE remind_date <= ? AND notified = 0
            ORDER BY remind_date, cell_name, freeze_date
        """, (today,))
        to_notify = cursor.fetchall()
        log_message(f"找到 {len(to_notify)} 条需要提醒的记录")

        if not to_notify:
            log_message("没有需要提醒的记录")
            if show_result:
                messagebox.showinfo("检查完成", "目前没有到期且尚未提醒的细胞。")
            return True

        grouped = {}
        for _, name, freeze_date, remind_date in to_notify:
            key = (name, freeze_date, remind_date)
            grouped[key] = grouped.get(key, 0) + 1

        lines = [
            "细胞冻存提醒",
            "",
            f"今天共有 {len(to_notify)} 支细胞需要转入液氮（{len(grouped)} 组）：",
            "",
        ]
        for index, ((name, freeze_date, remind_date), count) in enumerate(grouped.items(), 1):
            try:
                remind_date_obj = datetime.datetime.strptime(remind_date, "%Y-%m-%d").date()
                overdue_days = (today_date - remind_date_obj).days
                status = "今天到期" if overdue_days == 0 else f"已逾期 {overdue_days} 天"
            except (TypeError, ValueError):
                status = "已到提醒日期"
            lines.append(
                f"{index}. {name} × {count}｜冻存 {freeze_date}｜提醒 {remind_date}｜{status}"
            )
        lines.extend(["", "请尽快将以上细胞从 -80°C 冰箱转移至液氮罐中保存。"])

        msg = MIMEText("\n".join(lines), "plain", "utf-8")
        msg["Subject"] = f"细胞冻存提醒：{len(to_notify)} 支细胞需要转入液氮"
        msg["From"] = email_user
        msg["To"] = email_receiver

        server = smtplib.SMTP_SSL("smtp.zju.edu.cn", 994, timeout=30)
        server.login(email_user, email_password)
        server.sendmail(email_user, [email_receiver], msg.as_string())

        cursor.executemany(
            "UPDATE cell_records SET notified = 1 WHERE id = ?",
            [(record[0],) for record in to_notify]
        )
        conn.commit()
        log_message(f"提醒摘要发送成功，已标记 {len(to_notify)} 条记录")
        if show_result:
            messagebox.showinfo(
                "提醒已发送",
                f"已向 {email_receiver} 发送 1 封摘要邮件，"
                f"包含 {len(to_notify)} 支到期细胞。"
            )
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        log_message(f"邮件发送过程中发生错误: {e}")
        if show_result:
            messagebox.showerror(
                "发送失败",
                f"提醒邮件未发送，记录也未标记为已提醒。\n\n错误信息：{e}"
            )
        return False
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass
        if conn:
            conn.close()
        reminder_send_lock.release()

# ------------------- 定时器，每天检查提醒 -------------------
def startup_reminder_due(now=None):
    """程序在当天09:30之后启动时，需要立即执行一次补查。"""
    now = now or datetime.datetime.now()
    return now.time() >= datetime.time(9, 30)


def run_scheduler():
    if not email_reminders_enabled():
        log_message("邮件提醒未启用，不启动定时任务")
        return
    log_message("定时任务启动")
    schedule.clear("cryocell_reminders")
    schedule.every().day.at("09:30").do(send_reminders).tag("cryocell_reminders")
    # 运行期间定期补查，可覆盖电脑休眠、网络中断或错过09:30的情况。
    schedule.every(30).minutes.do(send_reminders).tag("cryocell_reminders")

    # 若程序在09:30之后才启动，当天立即补查，而不是错误地等到第二天。
    if startup_reminder_due():
        log_message("程序在09:30后启动，执行当日提醒补查")
        send_reminders()
    
    while running and email_reminders_enabled():
        try:
            schedule.run_pending()
            time.sleep(60)
        except Exception as e:
            log_message(f"后台定时任务异常：{e}")
            time.sleep(300)  # 出错后等待5分钟再试

    schedule.clear("cryocell_reminders")
    if running:
        log_message("邮件提醒已停用，定时任务线程已结束")


def ensure_scheduler_running():
    """仅在邮件启用时创建一个后台调度线程。"""
    global scheduler_thread
    if not email_reminders_enabled():
        return False
    if scheduler_thread is not None and scheduler_thread.is_alive():
        return True
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    log_message("定时任务线程已启动")
    return True

#-------------------关闭应用----------------
def on_closing():
    global running
    if messagebox.askokcancel("退出", "确定要退出CryoCell Reminder吗？"):
        running = False
        root.destroy()



# ------------------- 新增冻存盒管理界面 -------------------
def manage_boxes():
    class BoxManagerWindow:
        def __init__(self, parent):
            self.window = create_hidden_toplevel(parent)
            self.window.title("冻存盒管理")
            apply_modern_theme(self.window)
            fit_window(self.window, 820, 680, 640, 500)

            self.selected_pos = set()  # 🔥 🔥 🔥 这一行非常重要，初始化！
            self.tooltip = None  # 用于存储当前的提示框
            self.drag_source = None
            self.drag_start_xy = None
            self.dragging = False
            self.drag_ghost = None
            self.drag_animation_job = None
            self.drag_render_job = None
            self.drag_pending_xy = None
            self.drag_pulse = False
            self.drop_target = None
            self.cells = {}
            self.recording = False
            self.recording_started_at = None
            self.recorded_operations = []

            # 样式初始化
            style = ttk.Style()
            configure_box_grid_styles(style)

            # 冻存盒选择
            self.box_var = tk.StringVar()
            self.box_frame = tk.Frame(self.window, bg=APP_BG)
            self.box_frame.pack(fill=tk.X, padx=14, pady=(14, 8))

            ttk.Label(self.box_frame, text="冻存盒", font=(FONT_FAMILY, 11, "bold")).pack(side=tk.LEFT)
            self.box_combobox = ttk.Combobox(self.box_frame, textvariable=self.box_var, font=(FONT_FAMILY, 10), width=26, state="readonly")
            self.box_combobox.pack(side=tk.LEFT, padx=5)
            ttk.Button(self.box_frame, text="刷新列表", command=self.load_boxes).pack(side=tk.LEFT, padx=5)
            ttk.Button(self.box_frame, text="修改名称", command=self.rename_box).pack(side=tk.LEFT, padx=5) 
            self.box_combobox.bind("<<ComboboxSelected>>", self.on_box_changed)

            # 实体冻存盒整理操作记录
            self.record_frame = tk.Frame(
                self.window, bg=CARD_BG, padx=10, pady=7,
                highlightthickness=1, highlightbackground=BORDER_COLOR
            )
            self.record_frame.pack(fill=tk.X, padx=14, pady=(0, 4))
            self.record_button = ttk.Button(
                self.record_frame, text="开始记录整理操作",
                command=self.toggle_recording, style="Primary.TButton"
            )
            self.record_button.pack(side=tk.LEFT)
            self.record_status = tk.Label(
                self.record_frame, text="尚未开始记录", bg=CARD_BG,
                fg=TEXT_SECONDARY, font=(FONT_FAMILY, 9)
            )
            self.record_status.pack(side=tk.LEFT, padx=12)

            # 网格区
            self.grid_frame = tk.Frame(self.window, bg=APP_BG)
            self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)

            # 按钮区
            self.btn_frame = tk.Frame(self.window, bg=APP_BG)
            self.btn_frame.pack(pady=8)
            ttk.Button(self.btn_frame, text="取出细胞", command=self.release_position).pack(side=tk.LEFT, padx=5)
            ttk.Button(self.btn_frame, text="移动到其他冻存盒", command=self.move_to_other_box).pack(side=tk.LEFT, padx=5)
            ttk.Label(
                self.window,
                text="提示：按住有细胞的格子并拖到目标格；目标已有细胞时将交换位置",
                background=APP_BG,
                foreground=TEXT_SECONDARY
            ).pack(pady=(0, 8))

            self.create_grid()
            self.load_boxes()

            # 绑定窗口关闭事件
            self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        def center_window(self, win):
            win.update_idletasks()
            w = win.winfo_width()
            h = win.winfo_height()
            ws = win.winfo_screenwidth()
            hs = win.winfo_screenheight()
            x = (ws // 2) - (w // 2)
            y = (hs // 2) - (h // 2)
            win.geometry(f"{w}x{h}+{x}+{y}")

        def load_boxes(self):
            # 刷新列表后不保留旧选择，避免选中状态被带到其他冻存盒。
            self.clear_selection()
            boxes = get_boxes()
            self.box_dict = {f"{b[1]} (ID {b[0]})": b[0] for b in boxes}
            self.box_combobox['values'] = list(self.box_dict.keys())
            if self.box_dict:
                self.box_combobox.current(0)
                self.update_grid()
            else:
                messagebox.showinfo("提示", "当前没有可用冻存盒")

        def on_box_changed(self, event=None):
            """切换冻存盒时清除上一盒的选择状态。"""
            self.clear_selection()
            self.update_grid()

        def clear_selection(self):
            """清空选择集合，并按当前格子的真实状态恢复外观。"""
            old_selection = tuple(self.selected_pos)
            self.selected_pos.clear()
            for pos in old_selection:
                if hasattr(self, "buttons") and pos in self.buttons:
                    self.restore_button_style(pos)

        def create_grid(self):
            for widget in self.grid_frame.winfo_children():
                widget.destroy()
            self.buttons = {}
            self.button_positions = {}
            for index in range(9):
                self.grid_frame.rowconfigure(index, weight=1, uniform="box_rows")
                self.grid_frame.columnconfigure(index, weight=1, uniform="box_columns")
            for i, row in enumerate("ABCDEFGHI"):
                for j in range(1, 10):
                    pos = f"{row}{j}"
                    btn = ttk.Button(self.grid_frame, text=pos)
                    btn.grid(row=i, column=j-1, padx=2, pady=2, sticky="nsew")
                    btn.configure(command=lambda p=pos: self.select_position(p))
                    btn.bind("<ButtonPress-1>", lambda e, p=pos: self.start_drag(e, p))
                    btn.bind("<B1-Motion>", self.on_drag)
                    btn.bind("<ButtonRelease-1>", self.end_drag)
                    self.buttons[pos] = btn
                    self.button_positions[btn] = pos

        def update_grid(self):
            if not self.box_var.get():
                return

            try:
                box_id = self.box_dict[self.box_var.get()]
            except KeyError:
                return

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT position, cell_name, freeze_date 
                FROM cell_records 
                WHERE box_id = ? AND position IS NOT NULL
            """, (box_id,))
            cells = {pos: (name, date) for pos, name, date in cursor.fetchall()}
            conn.close()
            self.cells = cells

            for pos, btn in self.buttons.items():
                if pos in cells:
                    # 截断细胞名称以适应按钮
                    name = cells[pos][0]
                    display_name = name if len(name) <= 8 else name[:5] + "..."
                    btn.config(
                        text=f"{pos}\n{display_name}",
                        style="Selected.TButton" if pos in self.selected_pos else "Occupied.TButton"
                    )
                    
                    # 绑定鼠标事件显示完整名称
                    btn.bind("<Enter>", lambda e, p=pos, n=name: self.show_tooltip(e, p, n))
                    btn.bind("<Leave>", self.hide_tooltip)
                else:
                    btn.config(text=pos, style="Selected.TButton" if pos in self.selected_pos else "Empty.TButton")
                    # 移除绑定
                    btn.unbind("<Enter>")
                    btn.unbind("<Leave>")

        def start_drag(self, event, pos):
            """仅允许从有细胞的格子开始拖动。"""
            self.drag_source = pos if pos in self.cells else None
            self.drag_start_xy = (event.x_root, event.y_root)
            self.dragging = False
            self.drop_target = None

        def on_drag(self, event):
            if not self.drag_source or not self.drag_start_xy:
                return
            if not self.dragging:
                dx = abs(event.x_root - self.drag_start_xy[0])
                dy = abs(event.y_root - self.drag_start_xy[1])
                if max(dx, dy) < 6:
                    return
                self.dragging = True
                self.hide_tooltip(event)
                self.create_drag_ghost(event)
                self.animate_drag_source()

            self.schedule_drag_ghost(event.x_root, event.y_root)
            hovered_widget = self.window.winfo_containing(event.x_root, event.y_root)
            new_target = self.button_positions.get(hovered_widget)
            if new_target != self.drop_target:
                if self.drop_target and self.drop_target != self.drag_source:
                    self.restore_button_style(self.drop_target)
                self.drop_target = new_target
                if self.drop_target and self.drop_target != self.drag_source:
                    self.buttons[self.drop_target].config(style="DropTarget.TButton")

        def create_drag_ghost(self, event):
            """创建一个随鼠标移动的完整格子，让拖拽动作清晰可见。"""
            cell_name, freeze_date = self.cells[self.drag_source]
            display_name = cell_name if len(cell_name) <= 12 else cell_name[:9] + "..."
            self.drag_ghost = tk.Label(
                self.window,
                text=f"移动 {self.drag_source}\n{display_name}\n({freeze_date})",
                bg="#ffb74d",
                fg="#3e2723",
                relief="raised",
                borderwidth=3,
                padx=10,
                pady=6,
                font=(FONT_FAMILY, 9, "bold")
            )
            self.drag_ghost.place(
                x=event.x_root - self.window.winfo_rootx() + 18,
                y=event.y_root - self.window.winfo_rooty() + 18
            )
            self.drag_ghost.lift()

        def schedule_drag_ghost(self, x_root, y_root):
            """最多每 16ms 重绘一次拖拽浮层，避免高频鼠标事件造成卡顿。"""
            self.drag_pending_xy = (x_root, y_root)
            if self.drag_render_job is None:
                self.drag_render_job = self.window.after(16, self.render_drag_ghost)

        def render_drag_ghost(self):
            self.drag_render_job = None
            if not self.drag_ghost or not self.drag_pending_xy:
                return
            x_root, y_root = self.drag_pending_xy
            self.drag_ghost.place_configure(
                x=x_root - self.window.winfo_rootx() + 18,
                y=y_root - self.window.winfo_rooty() + 18
            )

        def animate_drag_source(self):
            """拖动期间让源格轻微脉动，形成持续的动态反馈。"""
            if not self.dragging or not self.drag_source:
                self.drag_animation_job = None
                return
            self.drag_pulse = not self.drag_pulse
            style = "DragSourcePulse.TButton" if self.drag_pulse else "DragSource.TButton"
            self.buttons[self.drag_source].config(style=style)
            self.drag_animation_job = self.window.after(180, self.animate_drag_source)

        def destroy_drag_feedback(self):
            if self.drag_animation_job:
                self.window.after_cancel(self.drag_animation_job)
                self.drag_animation_job = None
            if self.drag_render_job:
                self.window.after_cancel(self.drag_render_job)
                self.drag_render_job = None
            if self.drag_ghost:
                self.drag_ghost.destroy()
                self.drag_ghost = None
            self.drag_pending_xy = None
            self.drag_pulse = False

        def end_drag(self, event):
            if not self.dragging or not self.drag_source:
                self.drag_source = None
                self.drag_start_xy = None
                self.destroy_drag_feedback()
                return

            source_pos = self.drag_source
            hovered_widget = self.window.winfo_containing(event.x_root, event.y_root)
            target_pos = self.button_positions.get(hovered_widget) or self.drop_target
            self.drag_source = None
            self.drag_start_xy = None
            self.dragging = False
            self.destroy_drag_feedback()
            self.drop_target = None

            if target_pos and target_pos != source_pos:
                box_id = self.box_dict.get(self.box_var.get())
                if box_id is not None:
                    self.move_or_swap(box_id, source_pos, box_id, target_pos)
            self.update_grid()
            return "break"

        def restore_button_style(self, pos):
            if pos in self.selected_pos:
                style = "Selected.TButton"
            elif pos in self.cells:
                style = "Occupied.TButton"
            else:
                style = "Empty.TButton"
            self.buttons[pos].config(style=style)

        def toggle_recording(self):
            if self.recording:
                self.stop_and_export_recording()
            else:
                self.start_recording()

        def start_recording(self):
            """开始一次新的实体冻存盒整理记录会话。"""
            self.recorded_operations = []
            self.recording_started_at = datetime.datetime.now()
            self.recording = True
            self.record_button.config(text="停止记录并导出", style="Recording.TButton")
            self.update_record_status()
            log_message("开始记录冻存盒整理操作")

        def update_record_status(self):
            if self.recording:
                self.record_status.config(
                    text=f"● 正在记录 · {len(self.recorded_operations)} 步",
                    fg=DANGER
                )
            else:
                self.record_status.config(text="尚未开始记录", fg=TEXT_SECONDARY)

        def get_box_name(self, box_id):
            for display_name, known_id in self.box_dict.items():
                if known_id == box_id:
                    return display_name.split(" (ID")[0].strip()
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT box_name FROM freeze_boxes WHERE id = ?", (box_id,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else f"冻存盒{box_id}"

        def get_box_short_code(self, box_id):
            """将“冻存盒#1 (1-B-(-4))”压缩为操作单使用的“1”。"""
            box_name = self.get_box_name(box_id)
            match = re.search(r"冻存盒\s*#?\s*(\d+)", box_name, re.IGNORECASE)
            if not match:
                match = re.search(r"#\s*(\d+)", box_name)
            return match.group(1) if match else str(box_id)

        def record_operation(self, operation_type, instruction, cell_name,
                             source_box="", source_pos="", target_box="", target_pos=""):
            if not self.recording:
                return
            self.recorded_operations.append({
                "step": len(self.recorded_operations) + 1,
                "instruction": instruction,
                "type": operation_type,
                "cell_name": cell_name,
                "source_box": source_box,
                "source_pos": source_pos,
                "target_box": target_box,
                "target_pos": target_pos,
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
            })
            self.update_record_status()

        def stop_and_export_recording(self):
            """停止记录，并导出适合按顺序执行及 A4 打印的 Excel 操作单。"""
            if not self.recording:
                return True
            if not self.recorded_operations:
                self.recording = False
                self.recording_started_at = None
                self.record_button.config(text="开始记录整理操作", style="Primary.TButton")
                self.update_record_status()
                messagebox.showinfo("记录已停止", "本次没有产生需要导出的整理操作。", parent=self.window)
                return True

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filedialog.asksaveasfilename(
                parent=self.window,
                title="保存冻存盒整理操作单",
                initialdir=get_app_dir(),
                initialfile=f"冻存盒整理操作单_{timestamp}.xlsx",
                defaultextension=".xlsx",
                filetypes=[("Excel 工作簿", "*.xlsx")]
            )
            if not filename:
                return False

            try:
                from openpyxl import Workbook
                from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

                workbook = Workbook()
                sheet = workbook.active
                sheet.title = "整理操作单"
                sheet.merge_cells("A1:C1")
                sheet["A1"] = "冻存盒整理操作单"
                sheet["A1"].font = Font(name="Microsoft YaHei", size=20, bold=True, color="1D1D1F")
                sheet["A1"].alignment = Alignment(horizontal="center", vertical="center")
                sheet.row_dimensions[1].height = 36

                started = self.recording_started_at.strftime("%Y-%m-%d %H:%M:%S")
                finished = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sheet.merge_cells("A2:C2")
                sheet["A2"] = f"开始：{started}    完成：{finished}    共 {len(self.recorded_operations)} 步"
                sheet["A2"].alignment = Alignment(horizontal="center")
                sheet["A2"].font = Font(name="Microsoft YaHei", size=10, color="6E6E73")

                headers = ["步骤", "操作指令", "操作类型"]
                header_row = 4
                for column, title in enumerate(headers, 1):
                    cell = sheet.cell(header_row, column, title)
                    cell.font = Font(name="Microsoft YaHei", size=10, bold=True, color="FFFFFF")
                    cell.fill = PatternFill("solid", fgColor="007AFF")
                    cell.alignment = Alignment(horizontal="center", vertical="center")

                thin_gray = Side(style="thin", color="D1D1D6")
                for row_index, operation in enumerate(self.recorded_operations, header_row + 1):
                    values = [
                        operation["step"], operation["instruction"], operation["type"]
                    ]
                    for column, value in enumerate(values, 1):
                        cell = sheet.cell(row_index, column, value)
                        cell.font = Font(
                            name="Microsoft YaHei",
                            size=13 if column == 2 else 11,
                            bold=column == 2
                        )
                        cell.alignment = Alignment(
                            horizontal="center" if column != 2 else "left",
                            vertical="center", wrap_text=True
                        )
                        cell.border = Border(bottom=thin_gray)
                        if row_index % 2 == 0:
                            cell.fill = PatternFill("solid", fgColor="F5F5F7")
                    sheet.row_dimensions[row_index].height = 34

                widths = {"A": 10, "B": 34, "C": 14}
                for column, width in widths.items():
                    sheet.column_dimensions[column].width = width
                sheet.freeze_panes = "A5"
                sheet.auto_filter.ref = f"A4:C{header_row + len(self.recorded_operations)}"
                sheet.page_setup.orientation = "portrait"
                sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
                sheet.page_setup.fitToWidth = 1
                sheet.page_setup.fitToHeight = 0
                sheet.sheet_properties.pageSetUpPr.fitToPage = True
                sheet.print_title_rows = "1:4"
                sheet.print_area = f"A1:C{header_row + len(self.recorded_operations)}"
                sheet.oddFooter.center.text = "第 &P 页 / 共 &N 页"
                sheet.oddFooter.right.text = "CryoCell Reminder"
                workbook.save(filename)
            except Exception as e:
                messagebox.showerror("导出失败", f"操作记录仍保留，未能导出：\n{e}", parent=self.window)
                return False

            step_count = len(self.recorded_operations)
            self.recording = False
            self.recording_started_at = None
            self.record_button.config(text="开始记录整理操作", style="Primary.TButton")
            self.update_record_status()
            log_message(f"导出冻存盒整理操作单：{step_count}步，{filename}")
            messagebox.showinfo(
                "导出成功",
                f"已保存 {step_count} 步整理操作：\n{filename}",
                parent=self.window
            )
            self.recorded_operations = []
            return True

        def move_or_swap(self, source_box_id, source_pos, target_box_id, target_pos):
            """原子地移动一条记录；目标被占用时交换两条记录。"""
            conn = sqlite3.connect(DB_PATH)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, cell_name FROM cell_records WHERE box_id = ? AND position = ?",
                    (source_box_id, source_pos)
                )
                source = cursor.fetchone()
                if not source:
                    return False

                cursor.execute(
                    "SELECT id, cell_name FROM cell_records WHERE box_id = ? AND position = ?",
                    (target_box_id, target_pos)
                )
                target = cursor.fetchone()
                source_box_name = self.get_box_name(source_box_id)
                target_box_name = self.get_box_name(target_box_id)
                source_slot = f"{self.get_box_short_code(source_box_id)}{source_pos}"
                target_slot = f"{self.get_box_short_code(target_box_id)}{target_pos}"

                cursor.execute(
                    "UPDATE cell_records SET box_id = ?, position = ? WHERE id = ?",
                    (target_box_id, target_pos, source[0])
                )
                if target:
                    cursor.execute(
                        "UPDATE cell_records SET box_id = ?, position = ? WHERE id = ?",
                        (source_box_id, source_pos, target[0])
                    )
                    action = f"交换细胞位置：{source_pos}({source[1]}) ↔ {target_pos}({target[1]})"
                    operation_type = "交换"
                    instruction = f"{source_slot}↔{target_slot}"
                    recorded_cell_name = f"{source[1]} ↔ {target[1]}"
                else:
                    action = f"移动细胞：{source_pos}({source[1]}) → {target_pos}"
                    operation_type = "移动"
                    instruction = f"{source_slot}→{target_slot}"
                    recorded_cell_name = source[1]
                conn.commit()
                log_message(action)
                self.record_operation(
                    operation_type, instruction, recorded_cell_name,
                    source_box_name, source_pos, target_box_name, target_pos
                )
                return True
            except sqlite3.Error as e:
                conn.rollback()
                messagebox.showerror("移动失败", f"未能保存位置变更：\n{e}")
                return False
            finally:
                conn.close()

        def move_to_other_box(self):
            occupied = [pos for pos in self.selected_pos if pos in self.cells]
            if len(occupied) != 1:
                messagebox.showwarning("请选择源位置", "请先单击选择一个有细胞的格子，再移动到其他冻存盒。")
                return
            if len(self.box_dict) < 2:
                messagebox.showinfo("提示", "目前只有一个冻存盒，无法跨盒移动。")
                return

            source_pos = occupied[0]
            source_box_id = self.box_dict[self.box_var.get()]
            popup = create_hidden_toplevel(self.window)
            popup.title(f"移动 {source_pos} 到其他冻存盒")
            apply_modern_theme(popup)
            fit_window(popup, 780, 640, 620, 480)

            target_var = tk.StringVar()
            other_boxes = {name: box_id for name, box_id in self.box_dict.items() if box_id != source_box_id}
            header = tk.Frame(popup, bg=APP_BG)
            header.pack(fill=tk.X, padx=14, pady=10)
            tk.Label(header, text="目标冻存盒：", bg=APP_BG).pack(side=tk.LEFT)
            combo = ttk.Combobox(header, textvariable=target_var, values=list(other_boxes), state="readonly", width=30)
            combo.pack(side=tk.LEFT)
            grid = tk.Frame(popup, bg=APP_BG)
            grid.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))
            target_buttons = {}
            for index in range(9):
                grid.rowconfigure(index, weight=1, uniform="target_rows")
                grid.columnconfigure(index, weight=1, uniform="target_columns")

            def load_target_grid(event=None):
                target_box_id = other_boxes.get(target_var.get())
                if target_box_id is None:
                    return
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT position, cell_name FROM cell_records WHERE box_id = ? AND position IS NOT NULL",
                    (target_box_id,)
                )
                target_cells = dict(cursor.fetchall())
                conn.close()
                for pos, btn in target_buttons.items():
                    name = target_cells.get(pos)
                    display_name = name if name and len(name) <= 8 else (name[:5] + "..." if name else "")
                    btn.config(
                        text=f"{pos}\n{display_name}" if name else pos,
                        style="Occupied.TButton" if name else "Empty.TButton"
                    )

            def choose_target(pos):
                target_box_id = other_boxes.get(target_var.get())
                if target_box_id is None:
                    return
                if pos in self.get_occupied_positions(target_box_id):
                    if not messagebox.askyesno("交换位置", f"{pos} 已有细胞，是否交换两支细胞的位置？", parent=popup):
                        return
                if self.move_or_swap(source_box_id, source_pos, target_box_id, pos):
                    self.selected_pos.clear()
                    popup.destroy()
                    self.update_grid()

            for i, row in enumerate("ABCDEFGHI"):
                for j in range(1, 10):
                    pos = f"{row}{j}"
                    btn = ttk.Button(grid, text=pos, command=lambda p=pos: choose_target(p))
                    btn.grid(row=i, column=j-1, padx=2, pady=2, sticky="nsew")
                    target_buttons[pos] = btn

            combo.bind("<<ComboboxSelected>>", load_target_grid)
            combo.current(0)
            load_target_grid()
            popup.transient(self.window)
            popup.grab_set()

        def get_occupied_positions(self, box_id):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT position FROM cell_records WHERE box_id = ? AND position IS NOT NULL",
                (box_id,)
            )
            positions = {row[0] for row in cursor.fetchall()}
            conn.close()
            return positions

        def show_tooltip(self, event, pos, name):
            """显示细胞名称提示框"""
            if self.tooltip:
                self.tooltip.destroy()
                
            x = event.widget.winfo_rootx() + 20
            y = event.widget.winfo_rooty() - 30
            
            self.tooltip = tk.Toplevel(self.window)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.geometry(f"+{x}+{y}")
            
            label = tk.Label(self.tooltip, text=f"{pos}: {name}", 
                            bg="#ffffcc", fg="black", relief="solid", 
                            borderwidth=1, padx=5, pady=2, font=("Arial", 10))
            label.pack()

        def hide_tooltip(self, event):
            """隐藏提示框"""
            if self.tooltip:
                self.tooltip.destroy()
                self.tooltip = None

        def select_position(self, pos):
            if pos in self.selected_pos:
                self.selected_pos.remove(pos)
                self.restore_button_style(pos)
            else:
                self.selected_pos.add(pos)
                self.buttons[pos].config(style="Selected.TButton")

        def release_position(self):
            if not self.selected_pos:
                messagebox.showwarning("警告", "请先选择要操作的位置")
                return

            pos_list = "\n".join(self.selected_pos)
            confirm = messagebox.askyesno("确认操作", f"确定要取出以下位置的细胞吗？\n\n{pos_list}")
            if not confirm:
                return

            box_id = self.box_dict[self.box_var.get()]
            box_name = self.get_box_name(box_id)
            box_code = self.get_box_short_code(box_id)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            released_cells = []

            # 批量更新选中位置
            for pos in sorted(self.selected_pos):
                cursor.execute(
                    "SELECT cell_name FROM cell_records WHERE box_id = ? AND position = ?",
                    (box_id, pos)
                )
                row = cursor.fetchone()
                if not row:
                    continue
                released_cells.append((pos, row[0]))
                cursor.execute("""
                    UPDATE cell_records 
                    SET position = NULL 
                    WHERE box_id = ? AND position = ?
                """, (box_id, pos))
        
            conn.commit()
            conn.close()

            for pos, cell_name in released_cells:
                self.record_operation(
                    "取出", f"{box_code}{pos} OUT", cell_name,
                    box_name, pos
                )
            log_message(f"取出细胞：{len(released_cells)}个位置")
            self.selected_pos.clear()
            self.update_grid()

        def rename_box(self):
            """修改冻存盒名称"""
            selected = self.box_var.get()
            if not selected:
                messagebox.showwarning("警告", "请先选择一个冻存盒")
                return
                
            try:
                box_id = self.box_dict[selected]
            except KeyError:
                return
                
            # 获取当前名称（去除ID部分）
            current_name = selected.split(" (ID")[0].strip()
            
            popup = create_hidden_toplevel(self.window)
            popup.title("修改冻存盒名称")
            apply_modern_theme(popup)
            fit_window(popup, 430, 230, 340, 190)
            
            frame = tk.Frame(popup, bg=APP_BG, padx=24, pady=24)
            frame.pack(fill=tk.BOTH, expand=True)
            
            tk.Label(frame, text="新名称:", bg=APP_BG, font=(FONT_FAMILY, 11)).pack(pady=5)
            entry = tk.Entry(frame, font=(FONT_FAMILY, 11), width=FORM_TEXT_WIDTH)
            entry.insert(0, current_name)
            entry.pack(pady=5)
            entry.focus_set()
            
            def confirm_rename():
                new_name = entry.get().strip()
                if not new_name:
                    messagebox.showwarning("警告", "名称不能为空")
                    return
                    
                if new_name == current_name:
                    messagebox.showinfo("提示", "名称未改变")
                    popup.destroy()
                    return
                    
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("UPDATE freeze_boxes SET box_name = ? WHERE id = ?", (new_name, box_id))
                conn.commit()
                conn.close()
                
                log_message(f"修改冻存盒名称：{current_name} -> {new_name}")
                messagebox.showinfo("成功", f"冻存盒名称已更新为 '{new_name}'")
                popup.destroy()
                self.load_boxes()  # 刷新列表
                
            btn_frame = tk.Frame(frame, bg=APP_BG)
            btn_frame.pack(pady=10)
            
            ttk.Button(btn_frame, text="确认", command=confirm_rename, style="Primary.TButton").pack(side=tk.LEFT, padx=6)
            ttk.Button(btn_frame, text="取消", command=popup.destroy).pack(side=tk.LEFT, padx=6)
            
            popup.grab_set()
            
        def on_close(self):
            """关闭窗口时清除提示框"""
            if self.recording:
                choice = messagebox.askyesnocancel(
                    "整理记录尚未保存",
                    f"当前正在记录，共 {len(self.recorded_operations)} 步。\n\n"
                    "选择“是”停止并导出，选择“否”放弃记录，选择“取消”返回。",
                    parent=self.window
                )
                if choice is None:
                    return
                if choice and not self.stop_and_export_recording():
                    return
            if self.tooltip:
                self.tooltip.destroy()
            self.destroy_drag_feedback()
            self.window.destroy()

    BoxManagerWindow(root)


# ------------------- GUI界面构建 -------------------
def create_gui():
    global table, root, cell_count_label, search_var, email_label
    set_theme_palette(load_theme_preference())
    root = tk.Tk()
    root.withdraw()
    root.title("CryoCell Reminder - 细胞冻存管理")
    apply_modern_theme(root)
    install_button_focus_behavior(root)
    fit_window(root, 1120, 760, 720, 520)
    install_themed_messageboxes()
    root.protocol("WM_DELETE_WINDOW", on_closing)

    header = tk.Frame(root, bg=APP_BG)
    header.pack(fill=tk.X, padx=18, pady=(16, 6))
    tk.Label(
        header, text="CryoCell Reminder", bg=APP_BG, fg=TEXT_PRIMARY,
        font=(FONT_FAMILY, 18, "bold")
    ).pack(side=tk.LEFT)
    email_label = tk.Label(header, text="", bg=APP_BG, fg=TEXT_SECONDARY, font=(FONT_FAMILY, 9))
    email_label.pack(side=tk.RIGHT)
    update_email_label()

    toolbar = tk.Frame(root, bg=CARD_BG, padx=8, pady=8, highlightthickness=1, highlightbackground=BORDER_COLOR)
    toolbar.pack(side=tk.TOP, fill=tk.X, padx=18, pady=(0, 10))
    for column in range(7):
        toolbar.columnconfigure(column, weight=1, uniform="toolbar")

    ttk.Button(
        toolbar, text="关于",
        command=lambda: messagebox.showinfo("作者", "CryoCell Reminder v5.12\n作者: 威震八方@ZJU")
    ).grid(row=0, column=0, padx=3, sticky="ew")
    ttk.Button(toolbar, text="导出记录", command=export_to_excel).grid(row=0, column=1, padx=3, sticky="ew")
    ttk.Button(toolbar, text="添加细胞", command=add_record).grid(row=0, column=2, padx=3, sticky="ew")

    # 冻存盒管理按钮 + 弹出式菜单
    box_manage_btn = ttk.Button(toolbar, text="冻存盒管理")
    box_manage_btn.grid(row=0, column=3, padx=3, sticky="ew")

    box_menu = tk.Menu(
        root, tearoff=0, bg=CARD_BG, fg=TEXT_PRIMARY,
        activebackground=ACCENT, activeforeground=PRIMARY_TEXT, bd=0
    )
    box_menu.add_command(label="新建冻存盒", command=create_box)
    box_menu.add_command(label="删除冻存盒", command=delete_box)
    box_menu.add_command(label="管理冻存盒", command=manage_boxes)
    box_menu.add_command(label="导出盒子布局", command=export_box)
    box_menu.add_separator()
    box_menu.add_command(label="导入冻存盒…", command=import_boxes)
    box_menu.add_command(label="导出9×9导入模板", command=export_import_template)

    ttk.Button(toolbar, text="测试邮件", command=test_email).grid(row=0, column=4, padx=3, sticky="ew")

    def show_box_menu(event):
        box_menu.post(event.x_root, event.y_root)

    box_manage_btn.bind("<Button-1>", show_box_menu)

    ttk.Button(toolbar, text="邮箱设置", command=ask_email_info).grid(row=0, column=5, padx=3, sticky="ew")

    theme_var = tk.StringVar(value=CURRENT_THEME)
    theme_menu = tk.Menu(
        root, tearoff=0, bg=CARD_BG, fg=TEXT_PRIMARY,
        activebackground=ACCENT, activeforeground=PRIMARY_TEXT, bd=0
    )
    for theme_name, palette in THEMES.items():
        theme_menu.add_radiobutton(
            label=palette["label"], variable=theme_var, value=theme_name,
            command=lambda name=theme_name: switch_theme(name, root)
        )
    theme_button = ttk.Button(toolbar, text="主题")
    theme_button.grid(row=0, column=6, padx=3, sticky="ew")
    theme_button.bind("<Button-1>", lambda event: theme_menu.post(event.x_root, event.y_root))

    # 搜索区域
    search_frame = tk.Frame(root, bg=APP_BG)
    search_frame.pack(fill=tk.X, padx=18, pady=4)
    tk.Label(search_frame, text="搜索", bg=APP_BG, fg=TEXT_SECONDARY, font=(FONT_FAMILY, 10)).pack(side=tk.LEFT)
    search_var = tk.StringVar()
    search_entry = tk.Entry(
        search_frame, textvariable=search_var, font=(FONT_FAMILY, 11),
        relief="flat", bd=0, highlightthickness=1,
        highlightcolor=ACCENT, highlightbackground=BORDER_COLOR
    )
    search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0), ipady=6)
    search_var.trace("w", lambda *args: refresh_table())

    # 细胞数量显示
    cell_count_label = tk.Label(root, text="当前细胞数量：0", bg=APP_BG, font=(FONT_FAMILY, 10), fg=TEXT_SECONDARY)
    cell_count_label.pack(anchor="w", padx=18, pady=(4, 0))

    # 数据表格
    columns = ("细胞名称", "添加日期", "提醒日期", "状态", "冻存盒", "位置", "hidden_id")
    table_frame = ttk.Frame(root, style="Card.TFrame")
    table_frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=10)
    table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
    vertical_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=table.yview)
    horizontal_scroll = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=table.xview)
    table.configure(yscrollcommand=vertical_scroll.set, xscrollcommand=horizontal_scroll.set)

    for col in columns:
        table.heading(col, text=col, command=lambda c=col: sort_by(c, False))
        table.column(col, width=135 if col != "细胞名称" else 210, minwidth=80)
    table.grid(row=0, column=0, sticky="nsew")
    vertical_scroll.grid(row=0, column=1, sticky="ns")
    horizontal_scroll.grid(row=1, column=0, sticky="ew")
    table_frame.rowconfigure(0, weight=1)
    table_frame.columnconfigure(0, weight=1)

    # 右键菜单
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="删除记录", command=delete_record)

    def on_right_click(event):
        try:
            table.focus_set()  # 把焦点放到表格，防止有时候失焦
            row_id = table.identify_row(event.y)

            if row_id:  # 如果点到了一行
                if row_id not in table.selection():
                    table.selection_set(row_id)
            else:
                # 点击空白区域不改变已有选中
                pass

            # 无论如何弹出右键菜单
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    table.bind("<Button-3>", on_right_click)


    refresh_table()

    return root

#-------------------窗口居中------------------
def center_window(win):
    win.update_idletasks()
    w = win.winfo_width()
    h = win.winfo_height()
    ws = win.winfo_screenwidth()
    hs = win.winfo_screenheight()
    x = (ws // 2) - (w // 2)
    y = (hs // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")

# ------------------- 新增删除记录函数 -------------------
def delete_record():
    selected_items = table.selection()
    if not selected_items:
        messagebox.showwarning("提示", "请先选择要删除的记录")
        return

    if not messagebox.askyesno("确认删除", f"确定要删除选中的 {len(selected_items)} 条记录吗？"):
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for item in selected_items:
        record = table.item(item)
        record_id = record['values'][6]  # hidden_id列
        cursor.execute("DELETE FROM cell_records WHERE id = ?", (record_id,))
        table.delete(item)

    conn.commit()
    conn.close()
    refresh_table()
    messagebox.showinfo("删除成功", "选中的记录已成功删除！✅")


# ------------------- 工具函数 -------------------
def get_boxes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, box_name FROM freeze_boxes")
    boxes = cursor.fetchall()
    conn.close()
    return boxes

def log_message(message):
    with open("reminder_log.txt", "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        f.write(f"{timestamp} {message}\n")

# ------------------- 冻存盒管理菜单 -------------------
def box_management_menu(event=None):
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="新建冻存盒", command=create_box)
    menu.add_command(label="删除冻存盒", command=delete_box)
    menu.add_command(label="管理冻存盒", command=manage_boxes)
    menu.add_command(label="导出盒子布局", command=export_box)
    menu.post(event.x_root, event.y_root)

# ------------------- 删除冻存盒功能 -------------------
def delete_box():
    boxes = get_boxes()
    if not boxes:
        messagebox.showwarning("提示", "当前没有冻存盒可删除！")
        return

    box_dict = {f"{b[1]} (ID {b[0]})": b[0] for b in boxes}

    popup = create_hidden_toplevel(root)
    popup.title("删除冻存盒")
    apply_modern_theme(popup)
    fit_window(popup, 440, 250, 340, 200)

    frame = tk.Frame(popup, bg=APP_BG, padx=24, pady=24)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(frame, text="选择要删除的冻存盒:", bg=APP_BG, font=(FONT_FAMILY, 11)).pack(pady=10)
    box_var = tk.StringVar()
    combo = ttk.Combobox(
        frame, values=list(box_dict.keys()), textvariable=box_var,
        font=(FONT_FAMILY, 11), width=FORM_COMBO_WIDTH, state="readonly"
    )
    combo.pack()

    def confirm_delete():
        selected = box_var.get()
        if not selected:
            return
        box_id = box_dict[selected]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT cell_name, position FROM cell_records WHERE box_id = ?", (box_id,))
        cells = cursor.fetchall()

        if cells:
            examples = []
            for cell_name, position in cells[:6]:
                cell_name = cell_name or "未命名细胞"
                shown_name = cell_name if len(cell_name) <= 26 else f"{cell_name[:23]}…"
                examples.append(f"• {position or '未分配'}  {shown_name}")
            remaining = len(cells) - len(examples)
            if remaining:
                examples.append(f"…另有 {remaining} 条记录")
            box_name = selected.rsplit(" (ID ", 1)[0]
            warning_text = (
                f"“{box_name}”中仍有 {len(cells)} 条细胞记录。\n\n"
                + "\n".join(examples)
                + "\n\n删除冻存盒后，这些细胞记录会保留，"
                  "但冻存盒和位置信息将被清空。\n\n确定继续删除吗？"
            )
            confirm = messagebox.askyesno(
                "确认删除冻存盒", warning_text, parent=popup
            )
            if not confirm:
                conn.close()
                return

        cursor.execute("UPDATE cell_records SET box_id = NULL, position = NULL WHERE box_id = ?", (box_id,))
        cursor.execute("DELETE FROM freeze_boxes WHERE id = ?", (box_id,))
        conn.commit()
        conn.close()

        log_message(f"删除冻存盒：{selected}")
        refresh_table()
        messagebox.showinfo("删除成功", f"已删除 {selected}", parent=popup)
        popup.destroy()

    ttk.Button(frame, text="确认删除", command=confirm_delete).pack(pady=20)

#--------------------数据库备份功能-------------
def backup_database():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BASE_DIR, f"backup_{timestamp}.db")
    try:
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        log_message(f"数据库备份成功: {backup_path}")
    except Exception as e:
        log_message(f"数据库备份失败: {e}")

#--------------------数据库修复功能-------------
def repair_database():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("VACUUM")
        conn.close()
        log_message("数据库优化完成")
        return True
    except Exception as e:
        log_message(f"数据库优化失败: {e}")
        return False

# ------------------- 列排序功能 -------------------
def sort_by(col, descending):
    data = [(table.set(child, col), child) for child in table.get_children('')]
    try:
        data.sort(reverse=descending, key=lambda t: (t[0] if t[0] else "9999-99-99"))
    except:
        data.sort(reverse=descending)

    for index, (val, child) in enumerate(data):
        table.move(child, '', index)

    table.heading(col, command=lambda: sort_by(col, not descending))

# ------------------- 更新邮箱信息 -------------------
def update_email_label():
    config = load_email_config()
    try:
        enabled = email_reminders_enabled(config)
        if enabled and email_label.winfo_exists():
            email_label.config(text=f"当前邮箱: {config['EMAIL_USER']}")
        elif email_label.winfo_exists():
            email_label.config(text="邮件提醒：未启用")
        if manual_reminder_button is not None and manual_reminder_button.winfo_exists():
            manual_reminder_button.config(
                state=tk.NORMAL if enabled else tk.DISABLED
            )
    except (NameError, tk.TclError):
        # 主界面尚未建立时无需更新。
        pass





# ------------------- 主程序入口 -------------------
if __name__ == "__main__":
    # 供打包后验证单文件解压与 Python 入口是否完整，不触碰数据库或邮箱。
    if "--smoke-test" in sys.argv:
        sys.exit(0)

    # 初始化数据库
    if not init_db():
        # 数据库初始化失败，退出程序
        exit(1)
    
    # 首次启动可配置邮箱，也可明确选择不启用。
    if load_email_config() is None:
        ask_email_info()

    # 仅在用户启用邮件提醒时启动后台定时任务。
    ensure_scheduler_running()
    
    # 创建GUI
    app = create_gui()
    
    # 添加手动发送按钮
    manual_frame = tk.Frame(app, bg=APP_BG)
    manual_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10))
    
    manual_reminder_button = ttk.Button(
        manual_frame, text="立即检查提醒", command=lambda: send_reminders(show_result=True),
        style="Primary.TButton"
    )
    manual_reminder_button.pack()
    update_email_label()
    
    app.mainloop()

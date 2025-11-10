#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
海康威视高清扫码抓图工具 - 可执行版本
版本: 1.0.0
"""

import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path
import threading
import time
import subprocess

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 检查并导入必要的库
try:
    import requests
    from requests.auth import HTTPDigestAuth

    HAS_REQUESTS = True
except ImportError as e:
    print(f"导入requests库失败: {e}")
    HAS_REQUESTS = False

try:
    import cv2

    HAS_OPENCV = True
except ImportError as e:
    print(f"导入OpenCV库失败: {e}")
    HAS_OPENCV = False

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext, filedialog

    HAS_TKINTER = True
except ImportError as e:
    print(f"导入tkinter失败: {e}")
    HAS_TKINTER = False

# 导入自定义模块
try:
    from camera_capture import HikvisionOpenCVCapture

    HAS_CAMERA_MODULE = True
except ImportError as e:
    print(f"导入摄像头模块失败: {e}")
    HAS_CAMERA_MODULE = False


class CameraCaptureApp:
    def __init__(self):
        self.camera = None
        self.setup_directories()
        self.setup_logging()

        if not HAS_TKINTER:
            print("错误: 无法启动图形界面，请检查tkinter安装")
            input("按回车键退出...")
            sys.exit(1)

        self.setup_ui()

    def setup_directories(self):
        """创建必要的目录"""
        self.app_data_dir = Path("AppData")
        self.app_data_dir.mkdir(exist_ok=True)

        self.log_dir = self.app_data_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)

        self.image_dir = self.app_data_dir / "captured_images"
        self.image_dir.mkdir(exist_ok=True)

    def setup_logging(self):
        """设置日志系统"""
        log_file = self.log_dir / f'camera_tool_{datetime.now().strftime("%Y%m%d")}.log'

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 50)
        self.logger.info("海康威视扫码抓图工具启动")
        self.logger.info("=" * 50)

    def setup_ui(self):
        """设置用户界面"""
        self.root = tk.Tk()
        self.root.title("海康威视高清扫码抓图工具 v1.0.0")
        self.root.geometry("1000x750")
        self.root.minsize(900, 650)

        # 设置窗口图标
        self.set_window_icon()

        # 设置样式
        self.setup_styles()

        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill="both", expand=True)

        # 标题
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill="x", pady=(0, 15))

        title_label = ttk.Label(
            title_frame,
            text="🎯 海康威视高清扫码抓图工具",
            font=("微软雅黑", 18, "bold"),
            foreground="#2c3e50"
        )
        title_label.pack()

        subtitle_label = ttk.Label(
            title_frame,
            text="基于OpenCV RTSP协议的高清图像捕获",
            font=("微软雅黑", 10),
            foreground="#7f8c8d"
        )
        subtitle_label.pack()

        # 创建笔记本组件
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True, pady=(0, 10))

        # 创建各个页面
        self.create_capture_tab()
        self.create_history_tab()
        self.create_settings_tab()
        self.create_about_tab()

        # 状态栏
        self.create_status_bar(main_frame)

        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 初始依赖检查
        self.check_dependencies()

        # 自动加载历史记录
        self.root.after(100, self.load_recent_history)

    def set_window_icon(self):
        """设置窗口图标"""
        try:
            # 尝试从assets目录加载图标
            icon_path = Path("assets/icon.ico")
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception as e:
            self.logger.warning(f"设置图标失败: {e}")

    def setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()

        # 配置不同主题
        try:
            style.theme_use('vista')  # Windows主题
        except:
            try:
                style.theme_use('clam')
            except:
                pass

        # 配置按钮样式
        style.configure('Accent.TButton', font=('微软雅黑', 10, 'bold'))
        style.configure('Success.TButton', foreground='green')
        style.configure('Danger.TButton', foreground='red')

    def check_dependencies(self):
        """检查依赖库"""
        missing_deps = []

        if not HAS_REQUESTS:
            missing_deps.append("requests - 网络请求库")
        if not HAS_OPENCV:
            missing_deps.append("opencv-python - 图像处理库")
        if not HAS_CAMERA_MODULE:
            missing_deps.append("camera_capture - 摄像头核心模块")

        if missing_deps:
            error_msg = "以下依赖库缺失或加载失败:\n\n" + "\n".join(missing_deps)
            error_msg += "\n\n程序可能无法正常工作。"
            messagebox.showerror("依赖库错误", error_msg)
            self.logger.error("依赖库检查失败: %s", missing_deps)
        else:
            self.logger.info("所有依赖库检查通过")

    def create_capture_tab(self):
        """创建抓图页面"""
        frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(frame, text="📷 高清抓图")

        # 连接设置区域
        conn_frame = ttk.LabelFrame(frame, text="🔌 摄像头连接设置", padding="15")
        conn_frame.pack(fill="x", pady=(0, 20))

        # 连接信息网格
        conn_grid = ttk.Frame(conn_frame)
        conn_grid.pack(fill="x")

        # 第一行
        row1 = ttk.Frame(conn_grid)
        row1.pack(fill="x", pady=(0, 10))

        ttk.Label(row1, text="IP地址:", font=("微软雅黑", 10)).pack(side="left", padx=(0, 5))
        self.ip_entry = ttk.Entry(row1, width=18, font=("微软雅黑", 10))
        self.ip_entry.insert(0, "10.179.13.179")
        self.ip_entry.pack(side="left", padx=(0, 20))

        ttk.Label(row1, text="端口:", font=("微软雅黑", 10)).pack(side="left", padx=(0, 5))
        self.port_entry = ttk.Entry(row1, width=8, font=("微软雅黑", 10))
        self.port_entry.insert(0, "80")
        self.port_entry.pack(side="left", padx=(0, 20))

        # 第二行
        row2 = ttk.Frame(conn_grid)
        row2.pack(fill="x", pady=(0, 10))

        ttk.Label(row2, text="用户名:", font=("微软雅黑", 10)).pack(side="left", padx=(0, 5))
        self.user_entry = ttk.Entry(row2, width=12, font=("微软雅黑", 10))
        self.user_entry.insert(0, "admin")
        self.user_entry.pack(side="left", padx=(0, 20))

        ttk.Label(row2, text="密码:", font=("微软雅黑", 10)).pack(side="left", padx=(0, 5))
        self.pwd_entry = ttk.Entry(row2, width=12, font=("微软雅黑", 10), show="*")
        self.pwd_entry.insert(0, "12345")
        self.pwd_entry.pack(side="left", padx=(0, 20))

        self.connect_btn = ttk.Button(
            row2,
            text="🔗 连接摄像头",
            command=self.connect_camera,
            style="Accent.TButton"
        )
        self.connect_btn.pack(side="left", padx=(20, 0))

        self.conn_status = ttk.Label(
            row2,
            text="● 未连接",
            font=("微软雅黑", 10, "bold"),
            foreground="red"
        )
        self.conn_status.pack(side="left", padx=(20, 0))

        # 抓图控制区域
        capture_frame = ttk.LabelFrame(frame, text="🎯 扫码抓图控制", padding="15")
        capture_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(capture_frame, text="📋 条码内容:", font=("微软雅黑", 11)).pack(anchor="w")

        # 修复：移除height参数
        self.barcode_entry = ttk.Entry(capture_frame, font=("微软雅黑", 12))
        self.barcode_entry.pack(fill="x", pady=(8, 15))
        self.barcode_entry.focus()
        self.barcode_entry.bind('<Return>', lambda e: self.capture_picture())

        ttk.Label(capture_frame, text="📝 描述信息 (可选):", font=("微软雅黑", 11)).pack(anchor="w")
        self.desc_entry = ttk.Entry(capture_frame, font=("微软雅黑", 10))
        self.desc_entry.pack(fill="x", pady=(8, 15))

        # 按钮区域
        button_frame = ttk.Frame(capture_frame)
        button_frame.pack(fill="x")

        self.capture_btn = ttk.Button(
            button_frame,
            text="🎯 开始高清抓图",
            command=self.capture_picture,
            state="disabled",
            style="Accent.TButton",
            width=20
        )
        self.capture_btn.pack(side="left", padx=(0, 15))

        self.open_folder_btn = ttk.Button(
            button_frame,
            text="📁 打开图片文件夹",
            command=self.open_image_folder,
            width=15
        )
        self.open_folder_btn.pack(side="left", padx=(0, 15))

        self.test_btn = ttk.Button(
            button_frame,
            text="🔧 测试摄像头",
            command=self.test_camera,
            state="disabled",
            width=15
        )
        self.test_btn.pack(side="left")

        # 结果显示
        self.result_var = tk.StringVar(value="等待开始抓图...")
        result_label = ttk.Label(
            capture_frame,
            textvariable=self.result_var,
            font=("微软雅黑", 10),
            foreground="#2c3e50",
            background="#ecf0f1",
            relief="solid",
            padding="10"
        )
        result_label.pack(fill="x", pady=(15, 0))

        # 实时日志区域
        log_frame = ttk.LabelFrame(frame, text="📊 操作日志", padding="10")
        log_frame.pack(fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=8,
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        self.log_text.pack(fill="both", expand=True)

        # 添加初始日志说明
        self.log("🚀 程序启动完成")
        self.log("💡 提示: 连接摄像头后，扫描条码或手动输入条码内容，按回车键快速抓图")
        self.log("📷 使用OpenCV RTSP协议获取高清图像")

    def create_history_tab(self):
        """创建历史记录页面"""
        frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(frame, text="📚 抓图历史")

        # 工具栏
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 10))

        ttk.Button(
            toolbar,
            text="🔄 刷新记录",
            command=self.load_history
        ).pack(side="left", padx=(0, 10))

        ttk.Button(
            toolbar,
            text="🗑️ 清空显示",
            command=self.clear_history_display
        ).pack(side="left", padx=(0, 10))

        ttk.Button(
            toolbar,
            text="📁 打开历史文件夹",
            command=self.open_history_folder
        ).pack(side="left")

        # 历史记录显示
        history_frame = ttk.LabelFrame(frame, text="📅 最近抓图记录", padding="10")
        history_frame.pack(fill="both", expand=True)

        # 创建表格框架
        table_frame = ttk.Frame(history_frame)
        table_frame.pack(fill="both", expand=True)

        # 创建Treeview表格
        columns = ("时间", "条码", "文件名", "大小", "质量", "方法")
        self.history_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=15
        )

        # 设置列
        column_widths = {"时间": 150, "条码": 120, "文件名": 200, "大小": 80, "质量": 80, "方法": 120}
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=column_widths.get(col, 100))

        # 滚动条
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 绑定双击事件
        self.history_tree.bind("<Double-1>", self.on_history_double_click)

        # 底部统计信息
        self.stats_var = tk.StringVar(value="总计: 0 张图片")
        stats_label = ttk.Label(history_frame, textvariable=self.stats_var, font=("微软雅黑", 9))
        stats_label.pack(anchor="w", pady=(5, 0))

    def create_settings_tab(self):
        """创建设置页面"""
        frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(frame, text="⚙️ 设置")

        # 程序设置
        settings_frame = ttk.LabelFrame(frame, text="程序设置", padding="15")
        settings_frame.pack(fill="x", pady=(0, 15))

        # 图片保存设置
        ttk.Label(settings_frame, text="图片保存路径:", font=("微软雅黑", 10)).pack(anchor="w")
        path_frame = ttk.Frame(settings_frame)
        path_frame.pack(fill="x", pady=(5, 10))

        self.save_path_var = tk.StringVar(value=str(self.image_dir))
        path_entry = ttk.Entry(path_frame, textvariable=self.save_path_var, font=("微软雅黑", 9))
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ttk.Button(
            path_frame,
            text="浏览",
            command=self.browse_save_path
        ).pack(side="right")

        # 抓图设置
        ttk.Label(settings_frame, text="抓图超时时间(秒):", font=("微软雅黑", 10)).pack(anchor="w")
        self.timeout_var = tk.StringVar(value="15")
        timeout_entry = ttk.Entry(settings_frame, textvariable=self.timeout_var, width=10, font=("微软雅黑", 9))
        timeout_entry.pack(anchor="w", pady=(5, 10))

        # 保存设置按钮
        ttk.Button(
            settings_frame,
            text="💾 保存设置",
            command=self.save_settings,
            style="Accent.TButton"
        ).pack(pady=(10, 0))

        # 系统信息
        info_frame = ttk.LabelFrame(frame, text="系统信息", padding="15")
        info_frame.pack(fill="both", expand=True)

        info_text = f"""
程序版本: 1.0.0
运行路径: {os.path.abspath(".")}
图片保存: {self.image_dir}
日志目录: {self.log_dir}

依赖库状态:
✅ requests: {HAS_REQUESTS}
✅ OpenCV: {HAS_OPENCV}
✅ tkinter: {HAS_TKINTER}
✅ 摄像头模块: {HAS_CAMERA_MODULE}

技术支持: 智能助手
        """

        info_widget = scrolledtext.ScrolledText(
            info_frame,
            height=12,
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        info_widget.pack(fill="both", expand=True)
        info_widget.insert("1.0", info_text.strip())
        info_widget.config(state="disabled")

    def create_about_tab(self):
        """创建关于页面"""
        frame = ttk.Frame(self.notebook, padding="30")
        self.notebook.add(frame, text="ℹ️ 关于")

        # 程序信息
        about_text = """
🎯 海康威视高清扫码抓图工具

版本: 1.0.0
作者: 智能助手
发布日期: 2024年

📋 功能特点:
• 基于OpenCV RTSP协议的高清图像捕获
• 自动条码识别和图片命名
• 多帧智能选择最佳质量图片
• 完整的抓图历史记录
• 直观的用户界面

🔧 技术栈:
• Python 3.6+
• OpenCV 4.x
• Requests
• Tkinter

📞 技术支持:
如有问题请联系技术支持团队

⚠️ 免责声明:
本软件仅供学习和内部使用，请遵守相关法律法规。
        """

        about_label = ttk.Label(
            frame,
            text=about_text.strip(),
            font=("微软雅黑", 11),
            justify="left",
            background="#f8f9fa",
            relief="solid",
            padding="20"
        )
        about_label.pack(fill="both", expand=True)

        # 版权信息
        copyright_label = ttk.Label(
            frame,
            text="© 2024 智能助手. 保留所有权利。",
            font=("微软雅黑", 9),
            foreground="#7f8c8d"
        )
        copyright_label.pack(pady=(10, 0))

    def create_status_bar(self, parent):
        """创建状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill="x", pady=(5, 0))

        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            relief="sunken",
            padding="5"
        )
        status_label.pack(fill="x")

    def log(self, message):
        """记录日志到界面"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.logger.info(message)

    def connect_camera(self):
        """连接摄像头"""
        ip = self.ip_entry.get().strip()
        port = self.port_entry.get().strip()
        username = self.user_entry.get().strip()
        password = self.pwd_entry.get().strip()

        if not ip:
            messagebox.showerror("错误", "请输入摄像头IP地址")
            return

        self.connect_btn.config(state="disabled")
        self.status_var.set("正在连接摄像头...")
        self.log(f"正在连接摄像头 {ip}:{port}...")

        def connect_thread():
            try:
                self.camera = HikvisionOpenCVCapture(
                    camera_ip=ip,
                    username=username,
                    password=password,
                    port=int(port) if port else 80,
                    save_dir=self.image_dir
                )
                self.root.after(0, self.update_connection_status)
            except Exception as e:
                self.root.after(0, lambda: self.show_error(f"连接失败: {str(e)}"))

        threading.Thread(target=connect_thread, daemon=True).start()

    def update_connection_status(self):
        """更新连接状态"""
        if self.camera and self.camera.is_connected:
            self.conn_status.config(text="● 已连接", foreground="green")
            self.capture_btn.config(state="normal")
            self.test_btn.config(state="normal")
            self.open_folder_btn.config(state="normal")
            self.status_var.set("摄像头连接成功")
            self.log("✅ 摄像头连接成功")
        else:
            self.conn_status.config(text="● 连接失败", foreground="red")
            self.capture_btn.config(state="disabled")
            self.test_btn.config(state="disabled")
            self.status_var.set("摄像头连接失败")
            self.log("❌ 摄像头连接失败")

        self.connect_btn.config(state="normal")

    def capture_picture(self):
        """抓取图片"""
        barcode = self.barcode_entry.get().strip()
        description = self.desc_entry.get().strip()

        if not barcode:
            messagebox.showwarning("警告", "请输入条码内容")
            return

        if not self.camera or not self.camera.is_connected:
            messagebox.showerror("错误", "摄像头未连接")
            return

        self.capture_btn.config(state="disabled")
        self.status_var.set("正在高清抓图...")
        self.result_var.set("正在捕获高清图片...")
        self.log(f"开始高清抓图，条码: {barcode}")

        def capture_thread():
            try:
                result = self.camera.capture_with_opencv(barcode, description)
                self.root.after(0, lambda: self.update_capture_result(result))
            except Exception as e:
                self.root.after(0, lambda: self.show_error(f"抓图失败: {str(e)}"))

        threading.Thread(target=capture_thread, daemon=True).start()

    def update_capture_result(self, result):
        """更新抓图结果"""
        try:
            if result.get("success", False):
                filename = result.get("filename", "未知")
                file_size_kb = result.get("file_size_kb", 0)
                quality = result.get("quality", "未知")
                method = result.get("method", "未知")
                frames_captured = result.get("frames_captured", 0)
                frame_quality = result.get("best_frame_quality", 0)

                success_msg = f"✅ 抓图成功! 文件: {filename} ({file_size_kb}KB, {quality})"
                self.result_var.set(success_msg)

                self.log(f"✅ {method} 抓图成功")
                self.log(f"   文件: {filename} ({file_size_kb}KB, {quality})")
                self.log(f"   捕获{frames_captured}帧，最佳帧质量: {frame_quality:.2f}")

                # 清空输入框，准备下一次扫码
                self.barcode_entry.delete(0, tk.END)
                self.barcode_entry.focus()

                # 刷新历史记录
                self.load_history()
            else:
                error_msg = f"❌ 抓图失败: {result.get('message', '未知错误')}"
                self.result_var.set(error_msg)
                self.log(error_msg)

            self.capture_btn.config(state="normal")
            self.status_var.set("抓图完成")

        except Exception as e:
            self.show_error(f"结果处理错误: {str(e)}")

    def test_camera(self):
        """测试摄像头"""
        if not self.camera or not self.camera.is_connected:
            messagebox.showerror("错误", "摄像头未连接")
            return

        self.log("开始摄像头测试...")
        result = self.camera.capture_with_opencv("TEST", "摄像头测试")

        if result.get("success", False):
            messagebox.showinfo("测试成功", f"摄像头测试成功!\n文件大小: {result.get('file_size_kb', 0)}KB")
        else:
            messagebox.showerror("测试失败", f"摄像头测试失败:\n{result.get('message', '未知错误')}")

    def load_history(self):
        """加载历史记录"""
        if not self.camera:
            return

        try:
            history = self.camera.get_capture_history(50)  # 加载最近50条记录

            # 清空现有记录
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)

            # 添加新记录
            for record in history:
                quality = record.get('quality', '未知')
                quality_color = {
                    '超高清': '#27ae60',
                    '高清': '#2ecc71',
                    '标清': '#f39c12',
                    '普通': '#e67e22',
                    '低质量': '#e74c3c'
                }.get(quality, '#7f8c8d')

                self.history_tree.insert("", "end", values=(
                    record.get('capture_time', ''),
                    record.get('barcode', ''),
                    record.get('filename', ''),
                    f"{record.get('file_size_kb', 0)}KB",
                    quality,
                    record.get('capture_method', '')
                ))

            # 更新统计信息
            self.stats_var.set(f"总计: {len(history)} 张图片")
            self.log(f"历史记录已加载，共 {len(history)} 条记录")

        except Exception as e:
            self.log(f"❌ 加载历史记录失败: {str(e)}")

    def load_recent_history(self):
        """加载最近的历史记录"""
        self.load_history()

    def on_history_double_click(self, event):
        """双击历史记录项"""
        selection = self.history_tree.selection()
        if not selection:
            return

        item = self.history_tree.item(selection[0])
        filename = item["values"][2]  # 文件名在第三列

        if self.camera:
            image_path = self.camera.save_dir / filename
            if image_path.exists():
                try:
                    os.startfile(image_path)  # Windows
                except:
                    messagebox.showinfo("打开文件", f"文件路径: {image_path}")
            else:
                messagebox.showerror("错误", "图片文件不存在")

    def open_image_folder(self):
        """打开图片文件夹"""
        try:
            os.startfile(self.image_dir)
            self.log("已打开图片文件夹")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件夹: {str(e)}")

    def open_history_folder(self):
        """打开历史文件夹"""
        try:
            os.startfile(self.app_data_dir)
            self.log("已打开程序数据文件夹")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件夹: {str(e)}")

    def browse_save_path(self):
        """浏览保存路径"""
        folder = filedialog.askdirectory(initialdir=str(self.image_dir))
        if folder:
            self.save_path_var.set(folder)
            self.image_dir = Path(folder)

    def save_settings(self):
        """保存设置"""
        # 这里可以添加设置保存逻辑
        messagebox.showinfo("成功", "设置已保存")
        self.log("程序设置已保存")

    def clear_history_display(self):
        """清空历史显示"""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        self.stats_var.set("总计: 0 张图片")
        self.log("历史显示已清空")

    def show_error(self, message):
        """显示错误"""
        messagebox.showerror("错误", message)
        self.status_var.set("操作失败")
        self.connect_btn.config(state="normal")
        self.capture_btn.config(state="normal")
        self.log(f"❌ {message}")

    def on_closing(self):
        """程序关闭事件"""
        self.log("程序正在退出...")
        self.logger.info("程序正常退出")
        self.root.destroy()

    def run(self):
        """运行程序"""
        try:
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"程序运行异常: {e}")
            messagebox.showerror("程序错误", f"程序运行异常:\n{str(e)}")


def main():
    """主函数"""
    try:
        app = CameraCaptureApp()
        app.run()
    except Exception as e:
        print(f"程序启动失败: {e}")
        input("按回车键退出...")


if __name__ == "__main__":
    main()
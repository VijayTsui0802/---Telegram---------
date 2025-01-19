import sys
import json
import time
import requests
import threading
import configparser
import logging
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QSpinBox, QLineEdit, QPushButton, QTextEdit,
    QLabel, QProgressBar, QMessageBox, QTableWidget, QTableWidgetItem,
    QSplitter, QHeaderView, QMenu, QTabWidget, QComboBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QSize
from modules import MissionAccountTab, ConfigTab, MissionAddTab
from modules.database import Database
import re

class ThreadPoolManager:
    """线程池管理器"""
    def __init__(self):
        self.workers = []  # 活动的工作线程
        self.threads = []  # 线程列表
        self.is_running = True
        self.results_lock = threading.Lock()
        self.results = {}  # 存储结果
        
    def add_worker(self, worker, thread):
        """添加工作线程"""
        self.workers.append(worker)
        self.threads.append(thread)
        
    def stop_all(self):
        """停止所有线程"""
        self.is_running = False
        for worker in self.workers:
            worker.stop()
        
    def wait_all(self):
        """等待所有线程完成"""
        for thread in self.threads:
            if thread.isRunning():
                thread.quit()
                thread.wait()
                
    def clear(self):
        """清理资源"""
        self.workers.clear()
        self.threads.clear()
        self.results.clear()

class RequestWorker(QObject):
    """请求处理线程"""
    request_finished = pyqtSignal(dict)  # 请求完成信号
    progress_updated = pyqtSignal(int, int)   # 进度更新信号(线程ID, 进度)
    log_message = pyqtSignal(str)        # 日志信息信号

    def __init__(self, worker_id, start_id, end_id, interval, cookie, token, history):
        super().__init__()
        self.worker_id = worker_id
        self.start_id = start_id
        self.end_id = end_id
        self.interval = interval
        self.cookie = cookie
        self.token = token
        self.history = history
        self.is_running = True

    def run(self):
        """运行线程"""
        total = self.end_id - self.start_id + 1
        current = 0

        self.log_message.emit(f"线程 {self.worker_id} 开始处理: {self.start_id} - {self.end_id}")

        for id in range(self.start_id, self.end_id + 1):
            if not self.is_running:
                break

            # 检查是否已经请求过
            if str(id) in self.history:
                self.log_message.emit(f"线程 {self.worker_id}: ID {id} 已经请求过，跳过")
                current += 1
                progress = int((current / total) * 100)
                self.progress_updated.emit(self.worker_id, progress)
                continue

            try:
                response = self.make_request(id)
                self.request_finished.emit(response)
                self.log_message.emit(f"线程 {self.worker_id}: ID {id} 请求完成")
            except Exception as e:
                self.log_message.emit(f"线程 {self.worker_id}: ID {id} 请求失败: {str(e)}")

            current += 1
            progress = int((current / total) * 100)
            self.progress_updated.emit(self.worker_id, progress)
            
            if self.is_running:
                time.sleep(self.interval)

    def make_request(self, id):
        """发送单个请求并返回响应"""
        url = f"http://konk.cc/tgcloud/account/account_mission"
        
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,th;q=0.8,zh-TW;q=0.7",
            "Connection": "keep-alive",
            "Cookie": f"PHPSESSID={self.cookie}",
            "Referer": "http://konk.cc/tgcloud_pc/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "X-KL-Ajax-Request": "Ajax_Request",
            "token": self.token
        }
        
        params = {
            "id": id,
            "page": 1,
            "limit": 100
        }
        
        response = requests.get(url, headers=headers, params=params, verify=False)
        response_data = response.json()
        # 在响应中添加请求参数
        response_data['params'] = params
        return response_data

    def stop(self):
        """停止线程"""
        self.is_running = False

class Config:
    """配置管理类"""
    def __init__(self):
        self.db = Database()
        self.history_file = Path("request_history.json")
        self._history = {}  # 添加内存缓存
        self.migrate_history()
        self.load_history()  # 加载历史记录到内存

    def migrate_history(self):
        """迁移历史数据"""
        if self.history_file.exists():
            self.db.migrate_from_json(str(self.history_file))
            # 迁移完成后可以重命名历史文件
            self.history_file.rename(self.history_file.with_suffix('.json.bak'))

    def load_history(self):
        """从数据库加载历史记录到内存"""
        try:
            # 获取所有账号
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.account_id, a.has_2fa, a.status, 
                           v.code, v.send_time, v.created_at
                    FROM accounts a
                    LEFT JOIN verification_codes v ON a.account_id = v.account_id
                    AND v.created_at = (
                        SELECT MAX(created_at)
                        FROM verification_codes
                        WHERE account_id = a.account_id
                    )
                ''')
                rows = cursor.fetchall()
                
                for row in rows:
                    account_id, has_2fa, status, code, send_time, created_at = row
                    self._history[str(account_id)] = {
                        'result': code if code else '',
                        'has_2fa': bool(has_2fa),
                        'request_time': created_at if created_at else '',
                        'imported_to_mission': status == 1
                    }
        except Exception as e:
            print(f"加载历史记录失败: {e}")

    @property
    def history(self):
        """提供历史记录访问接口"""
        return self._history

    def load_config(self):
        """加载配置"""
        # 检查是否需要初始化默认配置
        if self.db.get_config('initialized') is None:
            self.create_default_config()

    def create_default_config(self):
        """创建默认配置"""
        default_configs = {
            'General': {
                'start_id': '11312122',
                'end_id': '11312122',
                'request_interval': '1'
            },
            'Auth': {
                'cookie': '',
                'token': ''
            },
            'Request': {
                'url': 'http://konk.cc/tgcloud/account/account_mission',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'verify_ssl': 'False'
            }
        }
        
        for section, values in default_configs.items():
            for key, value in values.items():
                self.db.save_config(f"{section}.{key}", value)
        
        self.db.save_config('initialized', True)

    def get(self, section, key, fallback=None):
        """获取配置值"""
        try:
            value = self.db.get_config(f"{section}.{key}")
            return value if value is not None else fallback
        except Exception as e:
            print(f"获取配置失败 [{section}][{key}]: {str(e)}")
            return fallback

    def set(self, section, key, value):
        """设置配置值"""
        try:
            self.db.save_config(f"{section}.{key}", value)
        except Exception as e:
            print(f"设置配置失败 [{section}][{key}]: {str(e)}")

    def add_history(self, id, result, has_2fa, request_time, verification_code):
        """添加历史记录"""
        account_data = {
            'account_id': str(id),
            'has_2fa': has_2fa,
            'status': 3
        }
        self.db.save_account(account_data)
        
        # 如果有两步验证，从响应中提取验证码
        if has_2fa:
            try:
                self.db.save_verification_code(str(id), verification_code, request_time)
            except Exception as e:
                print(f"保存验证码失败: {e}")
        
        # 更新内存缓存
        self._history[str(id)] = {
            'result': result,
            'has_2fa': has_2fa,
            'request_time': request_time,
            'imported_to_mission': False
        }
        
    def mark_as_imported(self, id):
        """标记账号为已导入任务"""
        account_data = {
            'account_id': str(id),
            'status': 1
        }
        self.db.save_account(account_data)
        
        # 更新内存缓存
        if str(id) in self._history:
            self._history[str(id)]['imported_to_mission'] = True
            
    def is_imported(self, id) -> bool:
        """检查账号是否已导入任务"""
        account = self.db.get_account(str(id))
        is_imported = account is not None and account.get('status', 0) == 1
        
        # 更新内存缓存
        if str(id) in self._history:
            self._history[str(id)]['imported_to_mission'] = is_imported
            
        return is_imported

    def get_history(self, id):
        """获取历史记录"""
        # 优先从内存缓存获取
        if str(id) in self._history:
            return self._history[str(id)]
            
        # 如果内存中没有，从数据库获取
        account = self.db.get_account(str(id))
        if not account:
            return None
            
        code_info = self.db.get_latest_verification_code(str(id))
        
        # 构建历史记录并缓存
        history = {
            'account_id': account['account_id'],
            'has_2fa': account['has_2fa'],
            'status': account['status'],
            'result': code_info['code'] if code_info else '',
            'request_time': code_info['created_at'] if code_info else '',
            'imported_to_mission': account['status'] == 1
        }
        
        self._history[str(id)] = history
        return history

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.setup_logging()  # 初始化日志系统
        self.worker = None
        self.work_thread = None
        self.config = Config()
        self.is_loading = False
        
        # 添加分页相关属性
        self.current_page = 1
        self.total_pages = 1
        self.page_size = 10  # 默认每页显示10条
        
        # 设置窗口图标
        icon = QIcon("assets/logo.ico")
        self.setWindowIcon(icon)
        # 设置任务栏图标
        app = QApplication.instance()
        if app:
            app.setWindowIcon(icon)
        
        # 加载样式表
        with open("modules/styles.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())
            
        # 设置窗口标题和大小
        self.setWindowTitle("TGCloud - Telegram云控系统")
        self.setMinimumSize(1200, 800)
        
        self.setup_ui()
        self.setup_connections()
        self.load_config_values()
        self.load_history_data()

    def setup_logging(self):
        """设置日志系统"""
        # 创建logs目录
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # 生成日志文件名（使用当前日期）
        current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"telegram_{current_date}.log"
        
        # 配置日志格式
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        # 记录程序启动日志
        logging.info("程序启动")

    def setup_ui(self):
        """设置UI界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 添加原有功能标签页
        self.main_tab = QWidget()
        self.setup_main_tab()
        self.tab_widget.addTab(self.main_tab, "账号采集")
        
        # 添加新的Mission Account标签页
        self.mission_account_tab = MissionAccountTab(config=self.config)
        self.tab_widget.addTab(self.mission_account_tab, "在线接码")
        
        # 添加新的Mission Add标签页
        self.mission_add_tab = MissionAddTab(config=self.config)
        self.tab_widget.addTab(self.mission_add_tab, "数据筛选")
        
        # 添加配置标签页（移到最后）
        self.config_tab = ConfigTab(self.config)
        self.tab_widget.addTab(self.config_tab, "配置")
        
        layout.addWidget(self.tab_widget)

    def setup_main_tab(self):
        """设置主标签页"""
        layout = QVBoxLayout(self.main_tab)
        
        # 任务配置区域
        task_group = QGroupBox("任务配置")
        task_layout = QHBoxLayout()
        
        # 起始ID
        start_id_layout = QHBoxLayout()
        start_id_layout.addWidget(QLabel("起始ID:"))
        self.start_id_spinbox = QSpinBox()
        self.start_id_spinbox.setRange(0, 999999999)
        self.start_id_spinbox.setValue(11312122)
        self.start_id_spinbox.setMinimumWidth(150)
        self.start_id_spinbox.setFixedWidth(150)
        start_id_layout.addWidget(self.start_id_spinbox)
        task_layout.addLayout(start_id_layout)
        
        # 结束ID
        end_id_layout = QHBoxLayout()
        end_id_layout.addWidget(QLabel("结束ID:"))
        self.end_id_spinbox = QSpinBox()
        self.end_id_spinbox.setRange(0, 999999999)
        self.end_id_spinbox.setValue(11312122)
        self.end_id_spinbox.setMinimumWidth(150)
        self.end_id_spinbox.setFixedWidth(150)
        end_id_layout.addWidget(self.end_id_spinbox)
        task_layout.addLayout(end_id_layout)
        
        # 请求间隔
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("请求间隔(秒):"))
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(0, 60)
        self.interval_spinbox.setValue(1)
        interval_layout.addWidget(self.interval_spinbox)
        task_layout.addLayout(interval_layout)
        
        # 线程数配置
        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel("线程数:"))
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setRange(1, 10)
        self.thread_spinbox.setValue(3)
        thread_layout.addWidget(self.thread_spinbox)
        task_layout.addLayout(thread_layout)
        
        task_group.setLayout(task_layout)
        layout.addWidget(task_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("开始")
        self.start_button.clicked.connect(self.start_requests)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.stop_requests)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        self.save_button = QPushButton("保存配置")
        self.save_button.clicked.connect(self.save_config_values)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
        
        # 线程进度区域
        self.thread_progress_group = QGroupBox("线程进度")
        self.thread_progress_layout = QVBoxLayout()
        self.thread_progress_bars = {}  # 存储线程进度条
        self.thread_progress_group.setLayout(self.thread_progress_layout)
        layout.addWidget(self.thread_progress_group)
        
        # 创建一个垂直分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)  # 防止分割部分被完全折叠
        layout.addWidget(splitter, 1)  # 添加拉伸因子1
        
        # 结果表格区域
        result_group = QGroupBox("结果")
        result_layout = QVBoxLayout()
        
        # 添加筛选区域
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "已导入", "未导入"])
        self.filter_combo.currentTextChanged.connect(self.filter_results)
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        result_layout.addLayout(filter_layout)
        
        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(5)
        self.result_table.setHorizontalHeaderLabels(["ID", "两步验证", "结果", "请求时间", "是否导入任务"])
        
        # 设置表格列的调整模式
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # ID列固定宽度
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)  # 两步验证列固定宽度
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # 结果列自适应
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # 请求时间列固定宽度
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # 是否导入任务列固定宽度
        
        # 设置固定宽度的列的具体宽度
        self.result_table.setColumnWidth(0, 80)  # ID列
        self.result_table.setColumnWidth(1, 80)  # 两步验证列
        self.result_table.setColumnWidth(3, 150)  # 请求时间列
        self.result_table.setColumnWidth(4, 100)  # 是否导入任务列
        
        # 其他表格属性
        self.result_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.result_table.customContextMenuRequested.connect(self.show_context_menu)
        self.result_table.verticalHeader().setVisible(False)  # 隐藏垂直表头
        self.result_table.setAlternatingRowColors(True)  # 启用交替行颜色
        
        result_layout.addWidget(self.result_table)
        
        # 分页控制
        page_control_layout = QHBoxLayout()
        
        # 每页显示数量
        page_size_layout = QHBoxLayout()
        page_size_layout.addWidget(QLabel("每页显示:"))
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(['10', '20', '50', '100'])
        self.page_size_combo.currentTextChanged.connect(self.on_page_size_changed)
        page_size_layout.addWidget(self.page_size_combo)
        page_control_layout.addLayout(page_size_layout)
        
        # 页码控制
        self.prev_page_btn = QPushButton("上一页")
        self.prev_page_btn.clicked.connect(self.prev_page)
        page_control_layout.addWidget(self.prev_page_btn)
        
        self.page_label = QLabel("1/1")
        page_control_layout.addWidget(self.page_label)
        
        self.next_page_btn = QPushButton("下一页")
        self.next_page_btn.clicked.connect(self.next_page)
        page_control_layout.addWidget(self.next_page_btn)
        
        result_layout.addLayout(page_control_layout)
        result_group.setLayout(result_layout)
        splitter.addWidget(result_group)
        
        # 日志区域
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout()
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        splitter.addWidget(log_group)
        
        # 设置分割器的初始大小比例
        splitter.setStretchFactor(0, 2)  # 表格区域占2
        splitter.setStretchFactor(1, 1)  # 日志区域占1

    def setup_connections(self):
        """设置信号连接"""
        # 配置更改信号
        self.config_tab.config_changed.connect(self.handle_config_changed)
        
        # 保存配置触发器
        self.start_id_spinbox.valueChanged.connect(lambda: self.save_config_values())
        self.end_id_spinbox.valueChanged.connect(lambda: self.save_config_values())
        self.interval_spinbox.valueChanged.connect(lambda: self.save_config_values())

    def handle_config_changed(self, config: dict):
        """处理配置更改"""
        # 更新认证信息
        auth_config = config
        if self.worker:
            self.worker.cookie = auth_config.get('cookie', '')
            self.worker.token = auth_config.get('token', '')

    def load_config_values(self):
        """从配置文件加载值"""
        try:
            self.is_loading = True
            # 加载基本设置
            self.start_id_spinbox.setValue(int(self.config.get('General', 'start_id', '11312122')))
            self.end_id_spinbox.setValue(int(self.config.get('General', 'end_id', '11312122')))
            self.interval_spinbox.setValue(int(self.config.get('General', 'request_interval', '1')))
        except Exception as e:
            print(f"加载配置时发生错误: {str(e)}")
            QMessageBox.warning(self, "错误", f"加载配置失败: {str(e)}")
        finally:
            self.is_loading = False

    def save_config_values(self):
        """保存值到配置文件"""
        if self.is_loading:
            return
            
        try:
            # 保存基本设置
            self.config.set('General', 'start_id', str(self.start_id_spinbox.value()))
            self.config.set('General', 'end_id', str(self.end_id_spinbox.value()))
            self.config.set('General', 'request_interval', str(self.interval_spinbox.value()))
        except Exception as e:
            print(f"保存配置时发生错误: {str(e)}")
            QMessageBox.warning(self, "错误", f"保存配置失败: {str(e)}")

    def start_requests(self):
        """开始请求"""
        self.append_log("开始执行请求...")
        
        if not self.validate_inputs():
            self.append_log("输入验证失败")
            return

        # 获取认证配置
        auth_config = self.config_tab.get_auth_config()
        self.append_log(f"获取认证配置: {auth_config}")
        
        if not auth_config['cookie'] or not auth_config['token']:
            self.append_log("错误: Cookie或Token未设置")
            QMessageBox.warning(self, "错误", "请在配置标签页中设置Cookie和Token")
            return

        # 清空表格
        self.result_table.setRowCount(0)
        
        # 清理旧的进度条和布局
        while self.thread_progress_layout.count():
            child = self.thread_progress_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.thread_progress_bars.clear()
        
        # 初始化线程池
        self.thread_pool = ThreadPoolManager()
        
        # 计算每个线程的ID范围
        start_id = self.start_id_spinbox.value()
        end_id = self.end_id_spinbox.value()
        thread_count = self.thread_spinbox.value()
        interval = self.interval_spinbox.value()
        
        id_range = end_id - start_id + 1
        ids_per_thread = id_range // thread_count
        remainder = id_range % thread_count
        
        current_start = start_id
        
        # 创建并启动工作线程
        for i in range(thread_count):
            # 计算当前线程的ID范围
            thread_ids = ids_per_thread + (1 if i < remainder else 0)
            thread_end = current_start + thread_ids - 1
            
            # 创建进度条
            progress_layout = QHBoxLayout()
            progress_layout.addWidget(QLabel(f"线程 {i+1}:"))
            progress_bar = QProgressBar()
            progress_bar.setTextVisible(True)
            self.thread_progress_bars[i+1] = progress_bar
            progress_layout.addWidget(progress_bar)
            self.thread_progress_layout.addLayout(progress_layout)
            
            # 创建工作线程
            worker = RequestWorker(
                worker_id=i+1,
                start_id=current_start,
                end_id=thread_end,
                interval=interval,
                cookie=auth_config['cookie'],
                token=auth_config['token'],
                history=self.config.history
            )
            
            # 创建线程
            thread = QThread()
            worker.moveToThread(thread)
            
            # 连接信号
            worker.request_finished.connect(self.handle_request_finished)
            worker.progress_updated.connect(self.update_thread_progress)
            worker.log_message.connect(self.append_log)
            thread.started.connect(worker.run)
            
            # 添加到线程池
            self.thread_pool.add_worker(worker, thread)
            
            # 启动线程
            thread.start()
            
            current_start = thread_end + 1
            
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def validate_inputs(self):
        """验证输入"""
        self.append_log("正在验证输入...")
        if self.start_id_spinbox.value() > self.end_id_spinbox.value():
            self.append_log(f"验证失败: 起始ID({self.start_id_spinbox.value()})大于结束ID({self.end_id_spinbox.value()})")
            QMessageBox.warning(self, "错误", "起始ID不能大于结束ID")
            return False
        
        self.append_log("输入验证通过")
        return True

    def stop_requests(self):
        """停止请求"""
        if hasattr(self, 'thread_pool'):
            self.thread_pool.stop_all()
            self.thread_pool.wait_all()
            self.append_log("正在停止所有线程...")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            # 清理资源
            self.thread_pool.clear()
            delattr(self, 'thread_pool')

    def handle_request_finished(self, response):
        """处理请求完成的响应"""
        try:
            current_time = time.strftime('%Y-%m-%d %H:%M:%S')
            row_position = self.result_table.rowCount()
            self.result_table.insertRow(row_position)
            
            if not isinstance(response, dict):
                self.result_table.setItem(row_position, 0, QTableWidgetItem("N/A"))
                self.result_table.setItem(row_position, 1, QTableWidgetItem("N/A"))
                self.result_table.setItem(row_position, 2, QTableWidgetItem("请求失败"))
                self.result_table.setItem(row_position, 3, QTableWidgetItem(current_time))
                self.result_table.setItem(row_position, 4, QTableWidgetItem("否"))
                self.append_log("请求失败: 无效的响应格式")
                return
            
            id = response.get('params', {}).get('id', 'N/A')
            if 'error' in response:
                self.result_table.setItem(row_position, 0, QTableWidgetItem(str(id)))
                self.result_table.setItem(row_position, 1, QTableWidgetItem("N/A"))
                self.result_table.setItem(row_position, 2, QTableWidgetItem(f"错误: {response['error']}"))
                self.result_table.setItem(row_position, 3, QTableWidgetItem(current_time))
                self.result_table.setItem(row_position, 4, QTableWidgetItem("否"))
                self.append_log(f"ID {id} 请求失败: {response['error']}")
                return
            
            # 设置ID
            id_item = QTableWidgetItem(str(id))
            self.result_table.setItem(row_position, 0, id_item)
            
            # 分析响应数据，提取两步验证信息
            response_str = json.dumps(response, ensure_ascii=False)
            verification_info = self.extract_2fa_info(response_str)
            has_2fa = verification_info['has_2fa']
            verification_code = verification_info['code']
            
            # 设置两步验证状态
            status_item = QTableWidgetItem('是' if has_2fa else '否')
            self.result_table.setItem(row_position, 1, status_item)
            
            # 设置请求结果
            display_result = verification_info['display_text'] if has_2fa else '否'
            result_item = QTableWidgetItem(display_result)
            result_item.setToolTip(response_str)
            result_item.setData(Qt.ItemDataRole.UserRole, response_str)
            self.result_table.setItem(row_position, 2, result_item)
            
            # 设置请求时间
            time_item = QTableWidgetItem(current_time)
            self.result_table.setItem(row_position, 3, time_item)
            
            # 设置是否导入任务（默认为否）
            imported_item = QTableWidgetItem("否")
            self.result_table.setItem(row_position, 4, imported_item)
            
            # 保存到历史记录
            try:
                self.config.add_history(id, response, has_2fa, current_time, verification_code)
                self.append_log(f"ID {id} 数据保存成功")
            except Exception as e:
                self.append_log(f"ID {id} 数据保存失败: {str(e)}")
            
            # 添加到日志
            self.append_log(f"ID {id} 请求完成: {response_str}")
            
        except Exception as e:
            self.append_log(f"处理响应时出错: {str(e)}")
            if row_position >= 0:
                self.result_table.setItem(row_position, 0, QTableWidgetItem("ERROR"))
                self.result_table.setItem(row_position, 1, QTableWidgetItem("N/A"))
                self.result_table.setItem(row_position, 2, QTableWidgetItem(f"处理错误: {str(e)}"))
                self.result_table.setItem(row_position, 3, QTableWidgetItem(current_time))
                self.result_table.setItem(row_position, 4, QTableWidgetItem("否"))

    def extract_2fa_info(self, response_str):
        """提取两步验证信息"""
        match = re.search(r'设置两步密码【(.+?)】成功', response_str)
        if match:
            return {
                'has_2fa': True,
                'code': match.group(1),
                'display_text': match.group(0)
            }
        return {
            'has_2fa': False,
            'code': None,
            'display_text': '否'
        }

    def update_thread_progress(self, thread_id, progress):
        """更新线程进度"""
        if thread_id in self.thread_progress_bars:
            self.thread_progress_bars[thread_id].setValue(progress)

    def append_log(self, message):
        """添加并保存日志"""
        # 添加到界面
        self.log_area.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )
        
        # 保存到日志文件
        logging.info(message)

    def show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu()
        copy_action = menu.addAction("复制完整内容")
        
        item = self.result_table.itemAt(position)
        if item and self.result_table.column(item) == 2:  # 只在结果列显示菜单
            action = menu.exec(self.result_table.viewport().mapToGlobal(position))
            if action == copy_action:
                # 获取完整的响应数据
                full_data = item.data(Qt.ItemDataRole.UserRole)
                if full_data:
                    clipboard = QApplication.clipboard()
                    clipboard.setText(full_data)

    def filter_results(self):
        """筛选结果"""
        filter_text = self.filter_combo.currentText()
        for row in range(self.result_table.rowCount()):
            imported = self.result_table.item(row, 4).text() if self.result_table.item(row, 4) else ""
            should_show = (
                filter_text == "全部" or
                (filter_text == "已导入" and imported == "是") or
                (filter_text == "未导入" and imported == "否")
            )
            self.result_table.setRowHidden(row, not should_show)

    def on_page_size_changed(self, value):
        """处理每页显示数量变化"""
        self.page_size = int(value)
        self.current_page = 1
        self.load_history_data()
        
    def prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_history_data()
        
    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_history_data()
            
    def load_history_data(self):
        """加载历史数据到表格"""
        try:
            # 清空表格
            self.result_table.setRowCount(0)
            
            # 获取所有历史记录
            history_items = list(self.config.history.items())
            total_records = len(history_items)
            
            # 设置每页显示数量
            self.page_size = int(self.page_size_combo.currentText())
            
            # 计算总页数
            self.total_pages = max(1, (total_records + self.page_size - 1) // self.page_size)
            
            # 确保当前页在有效范围内
            self.current_page = max(1, min(self.current_page, self.total_pages))
            
            # 计算当前页的数据范围
            start_idx = (self.current_page - 1) * self.page_size
            end_idx = min(start_idx + self.page_size, total_records)
            
            # 获取当前页的数据
            current_page_items = history_items[start_idx:end_idx]
            
            # 显示数据
            for account_id, data in current_page_items:
                row_position = self.result_table.rowCount()
                self.result_table.insertRow(row_position)
                
                # ID
                self.result_table.setItem(row_position, 0, QTableWidgetItem(str(account_id)))
                # 两步验证状态
                self.result_table.setItem(row_position, 1, QTableWidgetItem('是' if data['has_2fa'] else '否'))
                # 请求结果
                result_item = QTableWidgetItem(str(data['result']))
                if isinstance(data['result'], dict):
                    result_item.setData(Qt.ItemDataRole.UserRole, json.dumps(data['result'], ensure_ascii=False))
                self.result_table.setItem(row_position, 2, result_item)
                # 请求时间
                self.result_table.setItem(row_position, 3, QTableWidgetItem(str(data['request_time'])))
                # 是否导入任务
                self.result_table.setItem(row_position, 4, QTableWidgetItem('是' if data['imported_to_mission'] else '否'))
            
            # 更新页码显示
            self.page_label.setText(f"{self.current_page}/{self.total_pages}")
            
            # 更新按钮状态
            self.prev_page_btn.setEnabled(self.current_page > 1)
            self.next_page_btn.setEnabled(self.current_page < self.total_pages)
            
            # 显示记录总数
            self.append_log(f"当前显示第 {start_idx + 1} - {end_idx} 条记录，共 {total_records} 条")
                
        except Exception as e:
            error_msg = f"加载历史数据时发生错误: {str(e)}"
            print(error_msg)
            self.append_log(error_msg)
            QMessageBox.warning(self, "错误", error_msg)

if __name__ == "__main__":
    # 禁用SSL警告
    requests.packages.urllib3.disable_warnings()
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 
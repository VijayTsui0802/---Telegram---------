import sys
import json
import time
import requests
import configparser
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

    def add_history(self, id, result, has_2fa, request_time):
        """添加历史记录"""
        account_data = {
            'account_id': str(id),
            'has_2fa': has_2fa,
            'status': 0
        }
        self.db.save_account(account_data)
        
        if isinstance(result, dict) and 'code' in result:
            self.db.save_verification_code(str(id), result['code'], request_time)
        
        # 更新内存缓存
        self._history[str(id)] = {
            'result': result['code'] if isinstance(result, dict) and 'code' in result else result,
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

class RequestWorker(QObject):
    """请求处理线程"""
    request_finished = pyqtSignal(dict)  # 请求完成信号
    progress_updated = pyqtSignal(int)   # 进度更新信号
    log_message = pyqtSignal(str)        # 日志信息信号

    def __init__(self, start_id, end_id, interval, cookie, token, history):
        super().__init__()
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

        for id in range(self.start_id, self.end_id + 1):
            if not self.is_running:
                break

            # 检查是否已经请求过
            if str(id) in self.history:
                self.log_message.emit(f"ID {id} 已经请求过，跳过")
                current += 1
                progress = int((current / total) * 100)
                self.progress_updated.emit(progress)
                continue

            try:
                response = self.make_request(id)
                self.request_finished.emit(response)
                self.log_message.emit(f"ID {id} 请求完成: {json.dumps(response, ensure_ascii=False)}")
            except Exception as e:
                self.log_message.emit(f"ID {id} 请求失败: {str(e)}")

            current += 1
            progress = int((current / total) * 100)
            self.progress_updated.emit(progress)
            
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

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.worker = None
        self.work_thread = None
        self.config = Config()
        self.is_loading = False
        
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
        self.start_id_spinbox.setMinimumWidth(150)  # 设置最小宽度
        self.start_id_spinbox.setFixedWidth(150)    # 设置固定宽度
        start_id_layout.addWidget(self.start_id_spinbox)
        task_layout.addLayout(start_id_layout)
        
        # 结束ID
        end_id_layout = QHBoxLayout()
        end_id_layout.addWidget(QLabel("结束ID:"))
        self.end_id_spinbox = QSpinBox()
        self.end_id_spinbox.setRange(0, 999999999)
        self.end_id_spinbox.setValue(11312122)
        self.end_id_spinbox.setMinimumWidth(150)    # 设置最小宽度
        self.end_id_spinbox.setFixedWidth(150)      # 设置固定宽度
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
        
        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
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
        
        # 加载已有的历史记录到表格
        start_id = self.start_id_spinbox.value()
        end_id = self.end_id_spinbox.value()
        self.append_log(f"设置ID范围: {start_id} - {end_id}")
        
        for id in range(start_id, end_id + 1):
            history = self.config.get_history(str(id))
            if history:
                row_position = self.result_table.rowCount()
                self.result_table.insertRow(row_position)
                
                # ID
                self.result_table.setItem(row_position, 0, QTableWidgetItem(str(id)))
                # 两步验证状态
                self.result_table.setItem(row_position, 1, QTableWidgetItem('是' if history['has_2fa'] else '否'))
                # 请求结果
                self.result_table.setItem(row_position, 2, QTableWidgetItem(str(history['result'])))
                # 请求时间
                self.result_table.setItem(row_position, 3, QTableWidgetItem(str(history['request_time'])))
                # 是否导入任务
                self.result_table.setItem(row_position, 4, QTableWidgetItem('是' if history['imported_to_mission'] else '否'))
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)

        # 创建工作线程和worker
        self.work_thread = QThread()
        self.worker = RequestWorker(
            start_id,
            end_id,
            self.interval_spinbox.value(),
            auth_config['cookie'],
            auth_config['token'],
            self.config.history
        )
        
        # 将worker移动到工作线程
        self.worker.moveToThread(self.work_thread)
        
        # 连接信号
        self.worker.request_finished.connect(self.handle_request_finished)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.log_message.connect(self.append_log)
        self.work_thread.finished.connect(self.handle_worker_finished)
        self.work_thread.started.connect(self.worker.run)
        
        # 启动线程
        self.work_thread.start()
        self.append_log("工作线程已启动")

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
        if self.worker:
            self.worker.stop()
            self.append_log("正在停止请求...")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            # 清理资源
            if self.work_thread and self.work_thread.isRunning():
                self.work_thread.quit()
                self.work_thread.wait()
            self.worker = None
            self.work_thread = None

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
            
            # 使用正则表达式检查是否包含两步验证信息
            import re
            response_str = json.dumps(response, ensure_ascii=False)
            match = re.search(r'设置两步密码【(\d+)】成功', response_str)
            has_2fa = bool(match)
            
            # 设置两步验证状态
            status_item = QTableWidgetItem('是' if has_2fa else '否')
            self.result_table.setItem(row_position, 1, status_item)
            
            # 设置请求结果
            if has_2fa:
                display_result = match.group(0)
            else:
                display_result = '否'
                
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
            self.config.add_history(id, display_result, has_2fa, current_time)
            
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

    def handle_worker_finished(self):
        """处理工作线程完成"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.append_log("请求任务已完成")
        
        # 清理资源
        if self.work_thread and self.work_thread.isRunning():
            self.work_thread.quit()
            self.work_thread.wait()
        self.worker = None
        self.work_thread = None

    def append_log(self, message):
        """添加日志"""
        self.log_area.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

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

    def load_history_data(self):
        """加载历史数据到表格"""
        try:
            # 清空表格
            self.result_table.setRowCount(0)
            
            # 加载历史记录
            for account_id, data in self.config.history.items():
                row_position = self.result_table.rowCount()
                self.result_table.insertRow(row_position)
                
                # ID
                self.result_table.setItem(row_position, 0, QTableWidgetItem(str(account_id)))
                # 两步验证状态
                self.result_table.setItem(row_position, 1, QTableWidgetItem('是' if data['has_2fa'] else '否'))
                # 请求结果
                self.result_table.setItem(row_position, 2, QTableWidgetItem(str(data['result'])))
                # 请求时间
                self.result_table.setItem(row_position, 3, QTableWidgetItem(str(data['request_time'])))
                # 是否导入任务
                self.result_table.setItem(row_position, 4, QTableWidgetItem('是' if data['imported_to_mission'] else '否'))
                
        except Exception as e:
            print(f"加载历史数据时发生错误: {str(e)}")
            QMessageBox.warning(self, "错误", f"加载历史数据失败: {str(e)}")

if __name__ == "__main__":
    # 禁用SSL警告
    requests.packages.urllib3.disable_warnings()
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 
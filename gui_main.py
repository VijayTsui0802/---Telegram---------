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
from modules import MissionAccountTab, ConfigTab, MissionAddTab

class Config:
    """配置管理类"""
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config_file = Path("config.ini")
        self.history_file = Path("request_history.json")
        self.history = self.load_history()
        self.load_config()

    def load_history(self):
        """加载历史记录"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"加载历史记录失败: {str(e)}")
            return {}

    def save_history(self):
        """保存历史记录"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            print("保存历史记录成功")
        except Exception as e:
            print(f"保存历史记录失败: {str(e)}")

    def add_history(self, id, result, has_2fa, request_time):
        """添加历史记录"""
        self.history[str(id)] = {
            'result': result,
            'has_2fa': has_2fa,
            'request_time': request_time,
            'imported_to_mission': False  # 添加导入任务状态字段
        }
        self.save_history()
        
    def mark_as_imported(self, id):
        """标记账号为已导入任务"""
        if str(id) in self.history:
            self.history[str(id)]['imported_to_mission'] = True
            self.save_history()
            
    def is_imported(self, id) -> bool:
        """检查账号是否已导入任务"""
        return self.history.get(str(id), {}).get('imported_to_mission', False)

    def get_history(self, id):
        """获取历史记录"""
        return self.history.get(str(id))

    def load_config(self):
        """加载配置"""
        if self.config_file.exists():
            self.config.read(self.config_file, encoding='utf-8')
            print(f"加载配置文件: {self.config_file}")
            print(f"当前Auth配置: {dict(self.config['Auth']) if 'Auth' in self.config else 'None'}")
        else:
            print("配置文件不存在，创建默认配置")
            self.create_default_config()

    def _ensure_sections(self):
        """确保所有必要的配置节点存在"""
        if not self.config.has_section('General'):
            self.config['General'] = {
                'start_id': '11312122',
                'end_id': '11312122',
                'request_interval': '1'
            }
        
        if not self.config.has_section('Auth'):
            self.config['Auth'] = {
                'cookie': '',
                'token': ''
            }
        
        if not self.config.has_section('Request'):
            self.config['Request'] = {
                'url': 'http://konk.cc/tgcloud/account/account_mission',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'verify_ssl': 'False'
            }
        
        self.save_config()

    def create_default_config(self):
        """创建默认配置"""
        self.config['General'] = {
            'start_id': '11312122',
            'end_id': '11312122',
            'request_interval': '1'
        }
        self.config['Auth'] = {
            'cookie': '',
            'token': ''
        }
        self.config['Request'] = {
            'url': 'http://konk.cc/tgcloud/account/account_mission',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'verify_ssl': 'False'
        }
        self.save_config()

    def save_config(self):
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            print(f"保存配置成功: {dict(self.config['Auth']) if 'Auth' in self.config else 'None'}")
        except Exception as e:
            print(f"保存配置失败: {str(e)}")

    def get(self, section, key, fallback=None):
        """获取配置值"""
        try:
            value = self.config.get(section, key, fallback=fallback)
            print(f"获取配置 [{section}][{key}] = {value}")
            return value
        except Exception as e:
            print(f"获取配置失败 [{section}][{key}]: {str(e)}")
            return fallback

    def set(self, section, key, value):
        """设置配置值"""
        try:
            if not self.config.has_section(section):
                self.config.add_section(section)
            self.config.set(section, key, str(value))
            print(f"设置配置 [{section}][{key}] = {value}")
            self.save_config()
        except Exception as e:
            print(f"设置配置失败 [{section}][{key}]: {str(e)}")

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
        self.work_thread = None  # 改名为work_thread
        self.config = Config()
        self.is_loading = False
        
        # 加载样式表
        with open("modules/styles.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())
            
        # 设置窗口标题和大小
        self.setWindowTitle("控客 - Telegram云控系统")
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
        start_id_layout.addWidget(self.start_id_spinbox)
        task_layout.addLayout(start_id_layout)
        
        # 结束ID
        end_id_layout = QHBoxLayout()
        end_id_layout.addWidget(QLabel("结束ID:"))
        self.end_id_spinbox = QSpinBox()
        self.end_id_spinbox.setRange(0, 999999999)
        self.end_id_spinbox.setValue(11312122)
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
            history = self.config.get_history(id)
            if history:
                row_position = self.result_table.rowCount()
                self.result_table.insertRow(row_position)
                
                # ID
                self.result_table.setItem(row_position, 0, QTableWidgetItem(str(id)))
                # 两步验证状态
                self.result_table.setItem(row_position, 1, QTableWidgetItem('是' if history['has_2fa'] else '否'))
                # 请求结果
                self.result_table.setItem(row_position, 2, QTableWidgetItem(history['result']))
                # 请求时间
                self.result_table.setItem(row_position, 3, QTableWidgetItem(history['request_time']))
        
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
            for id, data in self.config.history.items():
                row_position = self.result_table.rowCount()
                self.result_table.insertRow(row_position)
                
                # ID
                self.result_table.setItem(row_position, 0, QTableWidgetItem(str(id)))
                # 两步验证状态
                self.result_table.setItem(row_position, 1, QTableWidgetItem('是' if data['has_2fa'] else '否'))
                # 请求结果
                self.result_table.setItem(row_position, 2, QTableWidgetItem(data['result']))
                # 请求时间
                self.result_table.setItem(row_position, 3, QTableWidgetItem(data['request_time']))
                # 是否导入任务
                self.result_table.setItem(row_position, 4, QTableWidgetItem('是' if data.get('imported_to_mission', False) else '否'))
                
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
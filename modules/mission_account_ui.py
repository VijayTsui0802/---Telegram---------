from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
    QPushButton, QTextEdit, QProgressBar, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QSpinBox, QComboBox, QApplication, QSplitter
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from datetime import datetime
from .mission_account import MissionAccountWorker
from PyQt6.QtGui import QColor
from .database import Database

class CodeWorker(QThread):
    """验证码获取工作线程"""
    code_updated = pyqtSignal(str, str, int)  # 验证码更新信号 (account_id, code, send_time)
    log_message = pyqtSignal(str)  # 日志信息信号
    
    def __init__(self, config, account_id):
        super().__init__()
        self.config = config
        self.account_id = account_id
        self.worker = MissionAccountWorker(config=config)
        # 连接worker的信号到本类的信号
        self.worker.code_updated.connect(self.code_updated)
        self.worker.log_message.connect(self.log_message)
        
    def run(self):
        """运行线程"""
        try:
            self.worker.get_verification_code(self.account_id)
        except Exception as e:
            self.log_message.emit(f"获取验证码出错: {e}")

class MissionAccountTab(QWidget):
    """Mission Account 标签页"""
    log_message_signal = pyqtSignal(str)  # 重命名信号
    
    def __init__(self, config=None):
        super().__init__()
        self.worker = None
        self.work_thread = None
        self.config = config
        self.code_timer = None
        self.is_getting_codes = False
        self.page_size = 10
        self.current_page = 1
        self.total_pages = 1
        self.db = Database()  # 添加数据库实例
        self.log_message_signal.connect(self.append_log)  # 连接信号到日志追加方法
        self.code_workers = []  # 初始化code_workers列表
        self.init_ui()
        self.load_data_from_db()  # 初始化时加载数据库数据
        
    def load_data_from_db(self):
        """从数据库加载数据"""
        try:
            # 获取当前页的数据
            result = self.db.get_all_accounts(self.current_page, self.page_size)
            
            # 更新总页数
            total_records = result.get('total', 0)
            self.total_pages = (total_records + self.page_size - 1) // self.page_size
            
            # 更新表格显示
            self.update_table_display(result.get('data', []))
            self.log_message(f"从数据库加载了 {len(result.get('data', []))} 条记录，共 {total_records} 条")
                
        except Exception as e:
            self.log_message(f"从数据库加载数据失败: {str(e)}")
            
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("开始获取")
        self.start_button.clicked.connect(self.start_process)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.stop_process)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        self.refresh_button = QPushButton("刷新数据")
        self.refresh_button.clicked.connect(self.refresh_data)
        button_layout.addWidget(self.refresh_button)
        
        self.clear_button = QPushButton("清除缓存")
        self.clear_button.clicked.connect(self.clear_data)
        button_layout.addWidget(self.clear_button)
        
        # 验证码获取按钮
        self.code_button = QPushButton("开始获取验证码")
        self.code_button.clicked.connect(self.toggle_code_getting)
        button_layout.addWidget(self.code_button)
        
        layout.addLayout(button_layout)
        
        # 进度区域
        progress_group = QGroupBox("进度")
        progress_layout = QVBoxLayout()
        
        progress_bar_layout = QHBoxLayout()
        self.progress_label = QLabel("进度:")
        progress_bar_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        progress_bar_layout.addWidget(self.progress_bar)
        
        progress_layout.addLayout(progress_bar_layout)
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # 创建一个垂直分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)  # 防止分割部分被完全折叠
        layout.addWidget(splitter, 1)  # 添加拉伸因子1
        
        # 结果表格区域
        result_group = QGroupBox("账号列表")
        result_layout = QVBoxLayout()
        
        self.account_table = QTableWidget()
        self.account_table.setColumnCount(13)  # 修改列数为13
        self.account_table.setHorizontalHeaderLabels([
            "序号",          # 0
            "账号ID",        # 1
            "账号名称",      # 2
            "任务状态",      # 3
            "账号状态",      # 4
            "分组",         # 5
            "成功次数",      # 6
            "失败次数",      # 7
            "创建时间",      # 8
            "更新时间",      # 9
            "两步密码",      # 10
            "验证码",        # 11
            "发送时间"       # 12
        ])
        
        # 设置表格列宽比例
        header = self.account_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)  # 所有列都参与自适应
        
        # 设置特定列的固定宽度
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # 序号
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)  # 账号ID
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)  # 成功次数
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)  # 失败次数
        
        self.account_table.setColumnWidth(0, 60)   # 序号
        self.account_table.setColumnWidth(1, 80)   # 账号ID
        self.account_table.setColumnWidth(6, 80)   # 成功次数
        self.account_table.setColumnWidth(7, 80)   # 失败次数
        
        # 设置表格其他属性
        self.account_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)  # 整行选择
        self.account_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)  # 单行选择
        self.account_table.setAlternatingRowColors(True)  # 交替行颜色
        self.account_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # 禁止编辑
        
        # 设置表格样式
        self.account_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f8f9fa;
                gridline-color: #e9ecef;
            }
            QTableWidget::item {
                padding: 5px;
                border: none;
                color: #2c3e50;  /* 默认文字颜色 */
            }
            QTableWidget::item:hover {
                background-color: #f0f7ff;  /* 鼠标悬停时的背景色 */
                color: #2c3e50;  /* 鼠标悬停时的文字颜色 */
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;  /* 选中时的背景色 */
                color: #2c3e50;  /* 选中时的文字颜色 */
            }
            QTableWidget::item:selected:hover {
                background-color: #e3f2fd;  /* 选中并悬停时的背景色 */
                color: #2c3e50;  /* 选中并悬停时的文字颜色 */
            }
            QTableWidget::item:selected:active {
                background-color: #e3f2fd;  /* 选中并激活时的背景色 */
                color: #2c3e50;  /* 选中并激活时的文字颜色 */
            }
        """)
        
        # 添加表格双击事件
        self.account_table.cellDoubleClicked.connect(self.copy_cell_content)
        
        result_layout.addWidget(self.account_table)
        
        # 分页控制（移到表格下方）
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
        # 设置固定高度为150像素
        self.log_area.setFixedHeight(150)
        # 设置最小宽度，但允许水平方向自适应
        self.log_area.setMinimumWidth(200)
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        
        # 不再将日志区域添加到分割器，而是直接添加到主布局
        layout.addWidget(log_group)
        
        self.setLayout(layout)
        
        # 初始化验证码获取定时器
        self.code_timer = QTimer()
        self.code_timer.timeout.connect(self.update_verification_codes)
        
    def toggle_code_getting(self):
        """切换验证码获取状态"""
        if not self.is_getting_codes:
            self.is_getting_codes = True
            # 禁用其他按钮
            self.start_button.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.clear_button.setEnabled(False)
            # 更改验证码按钮文本
            self.code_button.setText("停止获取验证码")
            self.code_timer.start(5000)  # 5秒更新一次
            self.update_verification_codes()  # 立即执行一次
        else:
            self.is_getting_codes = False
            # 启用其他按钮
            self.start_button.setEnabled(True)
            self.refresh_button.setEnabled(True)
            self.clear_button.setEnabled(True)
            # 更改验证码按钮文本
            self.code_button.setText("开始获取验证码")
            self.code_timer.stop()
            # 停止所有验证码获取线程
            for worker in self.code_workers:
                worker.quit()
                worker.wait()
            self.code_workers.clear()
            
    def update_verification_codes(self):
        """更新验证码"""
        if not self.is_getting_codes:
            return
            
        # 清理已完成的线程
        self.code_workers = [w for w in self.code_workers if not w.isFinished()]
            
        # 获取当前页的所有账号ID
        for row in range(self.account_table.rowCount()):
            account_id_item = self.account_table.item(row, 1)  # 账号ID列
            if account_id_item:
                account_id = account_id_item.text()
                # 检查是否已经有该账号的线程在运行
                if not any(w.account_id == account_id for w in self.code_workers):
                    # 创建新的工作线程
                    worker = CodeWorker(self.config, account_id)
                    worker.code_updated.connect(self.update_code_and_time)
                    worker.log_message.connect(self.log_message)
                    worker.start()
                    self.code_workers.append(worker)
                    self.log_message_signal.emit(f"开始获取账号 {account_id} 的验证码")
                    
    def update_code_and_time(self, account_id: str, code: str, send_time: int):
        """更新指定账号的验证码和发送时间"""
        for row in range(self.account_table.rowCount()):
            if self.account_table.item(row, 1).text() == account_id:  # 账号ID在第1列
                # 更新验证码列（第11列）和发送时间列（第12列）
                self.account_table.setItem(row, 11, QTableWidgetItem(code))
                # 更新发送时间 - 第12列
                time_str = datetime.fromtimestamp(send_time).strftime('%Y-%m-%d %H:%M:%S')
                self.account_table.setItem(row, 12, QTableWidgetItem(time_str))
                self.log_message_signal.emit(f"账号 {account_id} 的验证码已更新: {code}")
                break
                
    def on_page_size_changed(self, value):
        """处理每页显示数量变化"""
        self.page_size = int(value)
        self.current_page = 1
        self.load_data_from_db()
        
    def prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data_from_db()
        
    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_data_from_db()
            
    def update_table_display(self, accounts_data):
        """更新表格显示"""
        try:
            # 清空表格
            self.account_table.setRowCount(0)
            
            if not accounts_data:
                self.log_message("没有数据可显示")
                return
            
            # 显示当前页数据
            for idx, account in enumerate(accounts_data, start=1):
                row_position = self.account_table.rowCount()
                self.account_table.insertRow(row_position)
                
                # 序号
                self.account_table.setItem(row_position, 0, QTableWidgetItem(str(idx)))
                
                # 账号ID
                self.account_table.setItem(row_position, 1, QTableWidgetItem(str(account.get('account_id', ''))))
                
                # 账号名称
                self.account_table.setItem(row_position, 2, QTableWidgetItem(str(account.get('username', ''))))
                
                # 任务状态
                status_text = {
                    0: '未开始',
                    1: '进行中',
                    2: '已完成',
                    3: '已失败'
                }.get(account.get('status', 0), '未知')
                self.account_table.setItem(row_position, 3, QTableWidgetItem(status_text))
                
                # 账号状态
                account_status = {
                    0: '在线',
                    1: '离线',
                    2: '已删除',
                    3: '未知'
                }.get(account.get('account_status', 3), '未知')  # 默认显示未知
                self.account_table.setItem(row_position, 4, QTableWidgetItem(account_status))
                
                # 分组
                self.account_table.setItem(row_position, 5, QTableWidgetItem(str(account.get('group', ''))))
                
                # 成功/失败次数
                self.account_table.setItem(row_position, 6, QTableWidgetItem(str(account.get('msg_success_times', 0))))
                self.account_table.setItem(row_position, 7, QTableWidgetItem(str(account.get('msg_error_times', 0))))
                
                # 创建时间
                created_at = account.get('create_time_text', '')
                if not created_at or created_at == '-':
                    created_at = account.get('created_at', '')
                if created_at:
                    try:
                        if isinstance(created_at, str):
                            if 'Z' in created_at:
                                created_at = created_at.replace('Z', '+00:00')
                                created_at = datetime.fromisoformat(created_at).strftime('%Y-%m-%d %H:%M:%S')
                        elif isinstance(created_at, int):
                            created_at = datetime.fromtimestamp(created_at).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                self.account_table.setItem(row_position, 8, QTableWidgetItem(str(created_at)))
                
                # 更新时间
                updated_at = account.get('update_time_text', '')
                if not updated_at or updated_at == '-':
                    updated_at = account.get('updated_at', '')
                if updated_at:
                    try:
                        if isinstance(updated_at, str):
                            if 'Z' in updated_at:
                                updated_at = updated_at.replace('Z', '+00:00')
                                updated_at = datetime.fromisoformat(updated_at).strftime('%Y-%m-%d %H:%M:%S')
                        elif isinstance(updated_at, int):
                            updated_at = datetime.fromtimestamp(updated_at).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                self.account_table.setItem(row_position, 9, QTableWidgetItem(str(updated_at)))
                
                # 两步密码
                self.account_table.setItem(row_position, 10, QTableWidgetItem(str(account.get('two_step_password', ''))))
                
                # 验证码和发送时间
                code_info = account.get('verification_code', {})
                self.account_table.setItem(row_position, 11, QTableWidgetItem(str(code_info.get('code', ''))))
                send_time = code_info.get('send_time', '')
                if send_time:
                    try:
                        send_time = datetime.fromtimestamp(send_time).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                self.account_table.setItem(row_position, 12, QTableWidgetItem(str(send_time)))
                
                # 根据状态设置行颜色
                self.set_row_color(row_position, account.get('status', 0))
            
            # 更新页码显示
            self.page_label.setText(f"{self.current_page}/{self.total_pages}")
            
            # 更新按钮状态
            self.prev_page_btn.setEnabled(self.current_page > 1)
            self.next_page_btn.setEnabled(self.current_page < self.total_pages)
                
        except Exception as e:
            self.log_message(f"更新表格显示时出错: {str(e)}")
            raise
            
    def set_row_color(self, row: int, status: int):
        """设置行颜色"""
        colors = {
            0: QColor("#c8e6c9"),  # 在线 - 浅绿色
            1: QColor("#ffcdd2"),  # 离线 - 浅红色
            2: QColor("#ffecb3"),  # 已删除 - 浅黄色
            3: QColor("#ffffff")   # 未知 - 白色
        }
        
        color = colors.get(status, QColor("#ffffff"))
        for col in range(self.account_table.columnCount()):
            item = self.account_table.item(row, col)
            if item:
                item.setBackground(color)
        
        # 更新页码显示
        self.page_label.setText(f"{self.current_page}/{self.total_pages}")
        
        # 更新按钮状态
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages)
        
    def log_message(self, message: str):
        """发送日志消息"""
        self.log_message_signal.emit(message)
        
    def append_log(self, message: str):
        """添加日志消息到文本框"""
        self.log_area.append(message)
        # 滚动到底部
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )
        
    def update_progress(self, current: int, total: int):
        """更新进度条"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"进度: {current}/{total}")
        
    def process_finished(self, response: dict):
        """处理请求完成的响应"""
        try:
            if response.get('code') != 1:
                self.log_message(f"获取数据失败: {response.get('msg', '未知错误')}")
                return
            
            # 重新加载数据库中的所有数据
            self.current_page = 1
            self.load_data_from_db()
            
            # 恢复按钮状态
            self.cleanup()
            
        except Exception as e:
            self.log_message(f"处理响应数据时出错: {str(e)}")
            # 确保在出错时也恢复按钮状态
            self.cleanup()
            
    def cleanup(self):
        """清理资源并重置UI"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.refresh_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        
        # 停止所有验证码获取线程
        for worker in self.code_workers:
            worker.quit()
            worker.wait()
        self.code_workers.clear()
        
        if self.work_thread and self.work_thread.isRunning():
            self.work_thread.quit()
            self.work_thread.wait()
            
        self.worker = None
        self.work_thread = None
        
    def refresh_data(self):
        """刷新数据（忽略缓存重新获取）"""
        try:
            self.current_page = 1
            self.load_data_from_db()
            self.log_message("数据已刷新")
        except Exception as e:
            self.log_message(f"刷新数据失败: {e}")
            
    def clear_data(self):
        """清除缓存数据"""
        try:
            # 清空表格
            self.account_table.setRowCount(0)
            self.all_accounts = []
            self.total_pages = 1
            self.current_page = 1
            self.update_table_display()
            self.log_message("已清除数据")
        except Exception as e:
            self.log_message(f"清除缓存失败: {e}")
            
    def start_process(self):
        """开始处理"""
        # 清空表格
        self.account_table.setRowCount(0)
        self.all_accounts = []
        
        # 更新按钮状态
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.refresh_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        
        # 创建新的worker和线程
        self.worker = MissionAccountWorker(config=self.config)
        self.work_thread = QThread()
        self.worker.moveToThread(self.work_thread)
        
        # 连接信号
        self.worker.log_message.connect(self.log_message)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.request_finished.connect(self.process_finished)
        self.worker.code_updated.connect(self.update_code_and_time)
        
        # 处理完成后的清理
        self.work_thread.finished.connect(self.work_thread.deleteLater)
        
        # 启动线程
        self.work_thread.started.connect(self.worker.process_request)
        self.work_thread.start()
            
    def stop_process(self):
        """停止处理"""
        if self.worker:
            self.worker.stop()
            self.log_message("正在停止...")
            
            # 立即更新按钮状态
            self.cleanup()
            
            # 停止所有验证码获取线程
            if self.is_getting_codes:
                self.toggle_code_getting()  # 停止验证码获取
            
    def copy_cell_content(self, row, column):
        """双击单元格复制内容到剪贴板"""
        if column in [2, 10, 11]:  # 账号名称、两步密码和验证码列
            item = self.account_table.item(row, column)
            if item and item.text():
                QApplication.clipboard().setText(item.text())
                # 根据列类型显示不同的提示信息
                content_type = {
                    2: "账号名称",
                    10: "两步密码",
                    11: "验证码"
                }.get(column, "内容")
                self.log_message(f"已复制{content_type}到剪贴板: {item.text()}") 
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
    QPushButton, QTextEdit, QProgressBar, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QSpinBox, QComboBox
)
from PyQt6.QtCore import Qt, QThread, QTimer
from datetime import datetime
from .mission_account import MissionAccountWorker

class MissionAccountTab(QWidget):
    """Mission Account 标签页"""
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
        self.init_ui()
        
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
        
        layout.addLayout(page_control_layout)
        
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
        
        # 结果表格
        result_group = QGroupBox("账号列表")
        result_layout = QVBoxLayout()
        
        self.account_table = QTableWidget()
        self.account_table.setColumnCount(10)  # 增加了验证码和发送时间列
        self.account_table.setHorizontalHeaderLabels([
            "任务ID", "账号ID", "账号名称", "分组", "状态", 
            "添加次数", "添加数量", "更新时间", "验证码", "发送时间"
        ])
        self.account_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        result_layout.addWidget(self.account_table)
        result_group.setLayout(result_layout)
        layout.addWidget(result_group)
        
        # 日志区域
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout()
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        self.setLayout(layout)
        
        # 初始化验证码获取定时器
        self.code_timer = QTimer()
        self.code_timer.timeout.connect(self.update_verification_codes)
        
    def toggle_code_getting(self):
        """切换验证码获取状态"""
        if not self.is_getting_codes:
            self.is_getting_codes = True
            self.code_button.setText("停止获取验证码")
            self.code_timer.start(5000)  # 5秒更新一次
            self.update_verification_codes()  # 立即执行一次
        else:
            self.is_getting_codes = False
            self.code_button.setText("开始获取验证码")
            self.code_timer.stop()
            
    def update_verification_codes(self):
        """更新验证码"""
        if not self.is_getting_codes:
            return
            
        # 获取当前页的所有账号ID
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        
        for row in range(self.account_table.rowCount()):
            account_id_item = self.account_table.item(row, 1)  # 账号ID列
            if account_id_item:
                account_id = account_id_item.text()
                self.worker.get_verification_code(account_id)
                
    def update_code_and_time(self, account_id: str, code: str, send_time: int):
        """更新指定账号的验证码和发送时间"""
        for row in range(self.account_table.rowCount()):
            if self.account_table.item(row, 1).text() == account_id:
                # 更新验证码
                self.account_table.setItem(row, 8, QTableWidgetItem(code))
                # 更新发送时间
                time_str = datetime.fromtimestamp(send_time).strftime('%Y-%m-%d %H:%M:%S')
                self.account_table.setItem(row, 9, QTableWidgetItem(time_str))
                break
                
    def on_page_size_changed(self, value):
        """处理每页显示数量变化"""
        self.page_size = int(value)
        self.current_page = 1
        self.update_table_display()
        
    def prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.update_table_display()
        
    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.update_table_display()
            
    def update_table_display(self):
        """更新表格显示"""
        # 计算当前页要显示的数据范围
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        
        # 更新页码显示
        self.page_label.setText(f"{self.current_page}/{self.total_pages}")
        
        # 更新按钮状态
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages)
        
    def log_message(self, message: str):
        """添加日志消息"""
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
        if "error" in response:
            self.log_message(f"错误: {response['error']}")
            return
            
        # 更新账号表格
        if 'data' in response and 'data' in response['data']:
            accounts = response['data']['data']
            self.total_pages = (len(accounts) + self.page_size - 1) // self.page_size
            
            # 清空表格
            self.account_table.setRowCount(0)
            
            # 只显示当前页的数据
            start_idx = (self.current_page - 1) * self.page_size
            end_idx = min(start_idx + self.page_size, len(accounts))
            
            for account in accounts[start_idx:end_idx]:
                row = self.account_table.rowCount()
                self.account_table.insertRow(row)
                
                # 设置单元格数据
                self.account_table.setItem(row, 0, QTableWidgetItem(str(account['mission_id'])))
                self.account_table.setItem(row, 1, QTableWidgetItem(str(account['account_id'])))
                self.account_table.setItem(row, 2, QTableWidgetItem(account['name']))
                self.account_table.setItem(row, 3, QTableWidgetItem(account['group_name']))
                self.account_table.setItem(row, 4, QTableWidgetItem(account['status_text']))
                self.account_table.setItem(row, 5, QTableWidgetItem(str(account['add_contacts_times'])))
                self.account_table.setItem(row, 6, QTableWidgetItem(str(account['add_contacts_num'])))
                self.account_table.setItem(row, 7, QTableWidgetItem(account['update_time_text']))
                self.account_table.setItem(row, 8, QTableWidgetItem(""))  # 验证码列
                self.account_table.setItem(row, 9, QTableWidgetItem(""))  # 发送时间列
            
            self.update_table_display()
        
    def refresh_data(self):
        """刷新数据（忽略缓存重新获取）"""
        try:
            if self.worker and self.worker.data_file.exists():
                self.worker.data_file.unlink()  # 删除缓存文件
                self.log_message("已删除缓存数据，准备重新获取")
            self.start_process()  # 重新开始获取
        except Exception as e:
            self.log_message(f"刷新数据失败: {e}")
            
    def clear_data(self):
        """清除缓存数据"""
        try:
            # 清空表格
            self.account_table.setRowCount(0)
            
            # 删除缓存文件
            if self.worker and self.worker.data_file.exists():
                self.worker.data_file.unlink()
                self.log_message("已清除缓存数据")
            else:
                self.log_message("没有缓存数据需要清除")
        except Exception as e:
            self.log_message(f"清除缓存失败: {e}")
            
    def start_process(self):
        """开始处理"""
        # 清空表格
        self.account_table.setRowCount(0)
        
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
        self.work_thread.finished.connect(self.cleanup)
        
        # 启动线程
        self.work_thread.started.connect(self.worker.process_request)
        self.work_thread.start()
            
    def stop_process(self):
        """停止处理"""
        if self.worker:
            self.worker.stop()
            self.log_message("正在停止...")
            
    def cleanup(self):
        """清理资源并重置UI"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.refresh_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        
        if self.work_thread and self.work_thread.isRunning():
            self.work_thread.quit()
            self.work_thread.wait()
            
        self.worker = None
        self.work_thread = None 
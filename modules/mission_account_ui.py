from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
    QPushButton, QTextEdit, QProgressBar, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox
)
from PyQt6.QtCore import Qt, QThread
from .mission_account import MissionAccountWorker

class MissionAccountTab(QWidget):
    """Mission Account 标签页"""
    def __init__(self, config=None):
        super().__init__()
        self.worker = None
        self.work_thread = None
        self.config = config
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
        
        # 结果表格
        result_group = QGroupBox("账号列表")
        result_layout = QVBoxLayout()
        
        self.account_table = QTableWidget()
        self.account_table.setColumnCount(8)
        self.account_table.setHorizontalHeaderLabels([
            "任务ID", "账号ID", "账号名称", "分组", "状态", 
            "添加次数", "添加数量", "更新时间"
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
            for account in response['data']['data']:
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
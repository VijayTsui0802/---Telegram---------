from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import QThread
import sys
import os
import json

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulate_mission_add import MissionAddWorker

class MissionAddTab(QWidget):
    """Mission Add 任务界面"""
    def __init__(self, config=None):
        super().__init__()
        self.worker = None
        self.work_thread = None
        self.config = config
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout()
        
        # 选择模式区域
        mode_layout = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        
        self.history_radio = QRadioButton("使用历史成功账号")
        self.manual_radio = QRadioButton("手动输入账号")
        self.history_radio.setChecked(True)  # 默认选中使用历史记录
        
        self.mode_group.addButton(self.history_radio)
        self.mode_group.addButton(self.manual_radio)
        
        mode_layout.addWidget(self.history_radio)
        mode_layout.addWidget(self.manual_radio)
        
        # 账号输入区域
        input_layout = QHBoxLayout()
        self.account_label = QLabel("Account Items:")
        self.account_input = QLineEdit()
        self.account_input.setPlaceholderText("请输入account_items值")
        self.account_input.setEnabled(False)  # 默认禁用输入框
        input_layout.addWidget(self.account_label)
        input_layout.addWidget(self.account_input)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("开始请求")
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        
        # 日志区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        # 添加到主布局
        layout.addLayout(mode_layout)
        layout.addLayout(input_layout)
        layout.addLayout(button_layout)
        layout.addWidget(self.log_text)
        
        self.setLayout(layout)
        
        # 连接信号
        self.start_button.clicked.connect(self.start_request)
        self.stop_button.clicked.connect(self.stop_request)
        self.history_radio.toggled.connect(self.on_mode_changed)
        self.manual_radio.toggled.connect(self.on_mode_changed)
        
    def on_mode_changed(self):
        """处理模式切换"""
        use_history = self.history_radio.isChecked()
        self.account_input.setEnabled(not use_history)
        if use_history:
            self.account_input.clear()
        
    def start_request(self):
        """开始请求"""
        use_history = self.history_radio.isChecked()
        
        if not use_history:
            account_items = self.account_input.text().strip()
            if not account_items:
                self.log_text.append("错误: 请输入account_items值")
                return
            
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # 创建工作线程
        self.worker = MissionAddWorker(config=self.config)
        if not use_history:
            self.worker.account_items = self.account_input.text().strip()
            
        self.work_thread = QThread()
        self.worker.moveToThread(self.work_thread)
        
        # 连接信号
        self.worker.log_message.connect(self.log_message)
        self.worker.request_finished.connect(self.on_request_finished)
        self.work_thread.started.connect(lambda: self.worker.process_request(use_history))
        self.work_thread.finished.connect(self.work_thread.deleteLater)
        
        # 启动线程
        self.work_thread.start()
        
    def stop_request(self):
        """停止请求"""
        if self.worker:
            self.worker.stop()
            if self.work_thread and self.work_thread.isRunning():
                self.work_thread.quit()
                self.work_thread.wait()
            self.worker = None
            self.work_thread = None
            
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.account_input.setEnabled(not self.history_radio.isChecked())
        
    def log_message(self, message: str):
        """显示日志消息"""
        self.log_text.append(message)
        
    def on_request_finished(self, response: dict):
        """请求完成处理"""
        try:
            self.log_message(f"请求完成: {json.dumps(response, ensure_ascii=False)}")
            
            # 确保在主线程中更新UI
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.account_input.setEnabled(not self.history_radio.isChecked())
            
            # 清理资源
            if self.work_thread and self.work_thread.isRunning():
                self.work_thread.quit()
                self.work_thread.wait()
            
            self.worker = None
            self.work_thread = None
            
        except Exception as e:
            self.log_message(f"处理请求完成时出错: {str(e)}")
            # 确保按钮状态被重置
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False) 
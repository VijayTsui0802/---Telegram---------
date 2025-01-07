import requests
import urllib3
import json
import time
from pathlib import Path
import configparser
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QLineEdit,
    QSpinBox, QMessageBox, QComboBox, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class ConversationListWorker(QThread):
    """对话列表请求处理类"""
    log_message = pyqtSignal(str)  # 日志信息信号
    
    def __init__(self, account_id: int, query_type: str, page: int, limit: int, cookie: str, token: str):
        super().__init__()
        self.account_id = account_id
        self.query_type = query_type
        self.page = page
        self.limit = limit
        self.cookie = cookie
        self.token = token
        self.is_running = True
        
    def run(self):
        """运行线程"""
        try:
            self.make_request()
        except Exception as e:
            self.log_message.emit(f"请求出错: {e}")
            
    def make_request(self):
        """发送对话列表请求"""
        url = "http://konk.cc/tgcloud/account_operate/conversation_list"
        
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,th;q=0.8,zh-TW;q=0.7",
            "Connection": "keep-alive",
            "Cookie": f"PHPSESSID={self.cookie}",
            "Referer": "http://konk.cc/tgcloud_pc/?",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "X-KL-Ajax-Request": "Ajax_Request",
            "token": self.token
        }
        
        params = {
            "account_id": self.account_id,
            "query_type": self.query_type,
            "page": self.page,
            "limit": self.limit
        }
        
        try:
            # 禁用SSL验证警告
            urllib3.disable_warnings()
            
            # 发送GET请求
            response = requests.get(
                url, 
                headers=headers, 
                params=params,
                verify=False
            )
            
            # 解析响应
            response_data = response.json()
            self.log_message.emit(f"请求响应: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
            
        except Exception as e:
            self.log_message.emit(f"请求失败: {e}")

class ConversationListWindow(QWidget):
    """对话列表窗口"""
    def __init__(self):
        super().__init__()
        self.worker = None
        self.config = self.load_config()
        self.setup_ui()
        self.setWindowTitle("对话列表请求模拟器")
        
    def load_config(self):
        """加载配置"""
        config = configparser.ConfigParser()
        config_file = Path("config.ini")
        
        if config_file.exists():
            config.read(config_file, encoding='utf-8')
        else:
            config['Auth'] = {
                'cookie': '',
                'token': ''
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                config.write(f)
                
        return config
        
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout()
        
        # 认证配置区域
        auth_group = QGroupBox("认证配置")
        auth_layout = QVBoxLayout()
        
        cookie_layout = QHBoxLayout()
        cookie_layout.addWidget(QLabel("Cookie:"))
        self.cookie_input = QLineEdit()
        self.cookie_input.setText(self.config.get('Auth', 'cookie', fallback=''))
        cookie_layout.addWidget(self.cookie_input)
        auth_layout.addLayout(cookie_layout)
        
        token_layout = QHBoxLayout()
        token_layout.addWidget(QLabel("Token:"))
        self.token_input = QLineEdit()
        self.token_input.setText(self.config.get('Auth', 'token', fallback=''))
        token_layout.addWidget(self.token_input)
        auth_layout.addLayout(token_layout)
        
        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)
        
        # 请求参数区域
        params_group = QGroupBox("请求参数")
        params_layout = QVBoxLayout()
        
        # 账号ID输入
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Account ID:"))
        self.account_id_input = QSpinBox()
        self.account_id_input.setRange(0, 999999999)
        self.account_id_input.setValue(11321043)
        id_layout.addWidget(self.account_id_input)
        params_layout.addLayout(id_layout)
        
        # 查询类型选择
        query_type_layout = QHBoxLayout()
        query_type_layout.addWidget(QLabel("Query Type:"))
        self.query_type_combo = QComboBox()
        self.query_type_combo.addItems(["first", "next"])
        query_type_layout.addWidget(self.query_type_combo)
        params_layout.addLayout(query_type_layout)
        
        # 页码和每页数量
        page_layout = QHBoxLayout()
        page_layout.addWidget(QLabel("Page:"))
        self.page_input = QSpinBox()
        self.page_input.setRange(1, 9999)
        self.page_input.setValue(1)
        page_layout.addWidget(self.page_input)
        
        page_layout.addWidget(QLabel("Limit:"))
        self.limit_input = QSpinBox()
        self.limit_input.setRange(1, 100)
        self.limit_input.setValue(25)
        page_layout.addWidget(self.limit_input)
        params_layout.addLayout(page_layout)
        
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("开始请求")
        self.start_button.clicked.connect(self.start_request)
        button_layout.addWidget(self.start_button)
        
        self.save_button = QPushButton("保存配置")
        self.save_button.clicked.connect(self.save_config)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
        
        # 日志区域
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout()
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        self.setLayout(layout)
        
    def save_config(self):
        """保存配置"""
        try:
            self.config['Auth'] = {
                'cookie': self.cookie_input.text(),
                'token': self.token_input.text()
            }
            
            with open('config.ini', 'w', encoding='utf-8') as f:
                self.config.write(f)
                
            self.log_message("配置已保存")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存配置失败: {e}")
        
    def start_request(self):
        """开始请求"""
        # 获取输入
        cookie = self.cookie_input.text().strip()
        token = self.token_input.text().strip()
        account_id = self.account_id_input.value()
        query_type = self.query_type_combo.currentText()
        page = self.page_input.value()
        limit = self.limit_input.value()
        
        if not cookie or not token:
            QMessageBox.warning(self, "错误", "请输入Cookie和Token")
            return
            
        # 创建工作线程
        self.worker = ConversationListWorker(
            account_id=account_id,
            query_type=query_type,
            page=page,
            limit=limit,
            cookie=cookie,
            token=token
        )
        self.worker.log_message.connect(self.log_message)
        self.worker.finished.connect(self.handle_finished)
        
        # 更新按钮状态
        self.start_button.setEnabled(False)
        
        # 启动线程
        self.worker.start()
        
    def handle_finished(self):
        """处理请求完成"""
        self.start_button.setEnabled(True)
        self.worker = None
        
    def log_message(self, message: str):
        """添加日志消息"""
        self.log_area.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")
        # 滚动到底部
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

if __name__ == "__main__":
    # 禁用SSL警告
    urllib3.disable_warnings()
    
    app = QApplication([])
    window = ConversationListWindow()
    window.resize(800, 600)
    window.show()
    app.exec() 
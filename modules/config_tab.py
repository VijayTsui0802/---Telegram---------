from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

class ConfigTab(QWidget):
    """配置标签页"""
    # 定义配置更改信号
    config_changed = pyqtSignal(dict)  # 配置变更信号
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.init_ui()
        self.load_config()
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 认证配置组
        auth_group = QGroupBox("认证配置")
        auth_layout = QVBoxLayout()
        
        # Cookie配置
        cookie_layout = QHBoxLayout()
        cookie_layout.addWidget(QLabel("Cookie (PHPSESSID):"))
        self.cookie_input = QLineEdit()
        self.cookie_input.setPlaceholderText("输入PHPSESSID值")
        self.cookie_input.textChanged.connect(self.save_config)
        cookie_layout.addWidget(self.cookie_input)
        auth_layout.addLayout(cookie_layout)
        
        # Token配置
        token_layout = QHBoxLayout()
        token_layout.addWidget(QLabel("Token:"))
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("输入token值")
        self.token_input.textChanged.connect(self.save_config)
        token_layout.addWidget(self.token_input)
        auth_layout.addLayout(token_layout)
        
        # 保存按钮
        save_layout = QHBoxLayout()
        save_button = QPushButton("保存配置")
        save_button.clicked.connect(self.save_config)
        save_layout.addStretch()
        save_layout.addWidget(save_button)
        auth_layout.addLayout(save_layout)
        
        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)
        
        # 请求配置组
        request_group = QGroupBox("请求配置")
        request_layout = QVBoxLayout()
        
        # 基础URL说明
        url_label = QLabel("基础URL: http://konk.cc")
        url_label.setStyleSheet("color: gray;")
        request_layout.addWidget(url_label)
        
        # User-Agent说明
        ua_label = QLabel("默认User-Agent: Chrome/131.0.0.0")
        ua_label.setStyleSheet("color: gray;")
        request_layout.addWidget(ua_label)
        
        request_group.setLayout(request_layout)
        layout.addWidget(request_group)
        
        # 添加弹性空间
        layout.addStretch()
        
        self.setLayout(layout)
        
    def load_config(self):
        """加载配置"""
        try:
            # 加载认证信息
            cookie = self.config.get('Auth', 'cookie', '')
            token = self.config.get('Auth', 'token', '')
            
            self.cookie_input.setText(cookie)
            self.token_input.setText(token)
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载配置失败: {str(e)}")
            
    def save_config(self):
        """保存配置"""
        try:
            # 保存认证信息
            cookie = self.cookie_input.text().strip()
            token = self.token_input.text().strip()
            
            self.config.set('Auth', 'cookie', cookie)
            self.config.set('Auth', 'token', token)
            
            # 发送配置更改信号
            self.config_changed.emit({
                'cookie': cookie,
                'token': token
            })
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存配置失败: {str(e)}")
            
    def get_auth_config(self) -> dict:
        """获取认证配置"""
        return {
            'cookie': self.cookie_input.text().strip(),
            'token': self.token_input.text().strip()
        } 
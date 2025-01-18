import requests
import urllib3
import json
from typing import Dict, Any, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal
import re
from PyQt6.QtWidgets import QTableWidget, QHeaderView
from PyQt6.QtCore import Qt
from .database import Database

class MissionAccountWorker(QObject):
    """Mission Account 请求处理类"""
    request_finished = pyqtSignal(dict)  # 请求完成信号
    log_message = pyqtSignal(str)  # 日志信息信号
    progress_updated = pyqtSignal(int, int)  # 进度更新信号
    code_updated = pyqtSignal(str, str, int)  # 验证码更新信号 (account_id, code, send_time)
    
    def __init__(self, config=None):
        super().__init__()
        self.is_running = True
        self.config = config
        self.db = Database()
        
    def get_verification_code(self, account_id: str):
        """获取账号的验证码"""
        url = "http://konk.cc/tgcloud/account_operate/update_data"
        
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,th;q=0.8,zh-TW;q=0.7",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Cookie": f"PHPSESSID={self.config.get('Auth', 'cookie')}",
            "Origin": "http://konk.cc",
            "Referer": "http://konk.cc/tgcloud_pc/?",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "X-KL-Ajax-Request": "Ajax_Request",
            "token": self.config.get('Auth', 'token')
        }
        
        data = {
            "account_update_time": 0,
            "account_id": int(account_id),
            "conversation_update_time": 1
        }
        
        try:
            # 禁用SSL验证警告
            urllib3.disable_warnings()
            
            # 发送POST请求
            response = requests.post(
                url, 
                headers=headers, 
                json=data,
                verify=False
            )
            
            # 解析响应
            response_data = response.json()
            
            if response_data.get('code') == 1 and 'data' in response_data:
                conversation_list = response_data['data'].get('conversation_list', {})
                if 'new_data' in conversation_list and conversation_list['new_data']:
                    for conversation in conversation_list['new_data']:
                        near_msg = conversation.get('near_msg', '')
                        if near_msg:
                            # 解析JSON字符串
                            try:
                                msg_data = json.loads(near_msg)
                                message_text = msg_data.get('message', '')
                                
                                # 提取验证码
                                code_match = re.search(r'Login code: (\d+)', message_text)
                                if code_match:
                                    code = code_match.group(1)
                                    send_time = conversation.get('updatetime', 0)
                                    
                                    # 保存验证码到数据库
                                    self.db.save_verification_code(account_id, code, send_time)
                                    
                                    self.code_updated.emit(account_id, code, send_time)
                                    self.log_message.emit(f"获取到账号 {account_id} 的验证码: {code}")
                                    return
                            except json.JSONDecodeError:
                                continue
                
            self.log_message.emit(f"未找到账号 {account_id} 的验证码")
            
        except Exception as e:
            self.log_message.emit(f"获取验证码失败: {e}")

    def get_mission_list(self) -> Dict[str, Any]:
        """获取任务列表"""
        url = "http://konk.cc/tgcloud/mission/mission_list"
        
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,th;q=0.8,zh-TW;q=0.7",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Cookie": f"PHPSESSID={self.config.get('Auth', 'cookie')}",
            "Origin": "http://konk.cc",
            "Referer": "http://konk.cc/tgcloud_pc/?",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "X-KL-Ajax-Request": "Ajax_Request",
            "token": self.config.get('Auth', 'token')
        }
        
        data = {
            "map": {"type": "multi_msg"},
            "page": 1,
            "limit": 10
        }
        
        try:
            # 禁用SSL验证警告
            urllib3.disable_warnings()
            
            # 发送POST请求
            response = requests.post(
                url, 
                headers=headers, 
                json=data,
                verify=False
            )
            
            # 解析响应
            response_data = response.json()
            
            # 保存任务列表到数据库
            if response_data.get('code') == 1 and 'data' in response_data:
                for mission in response_data['data'].get('data', []):
                    self.db.save_mission(mission)
                    
            return response_data
            
        except Exception as e:
            return {"error": str(e)}
            
    def get_mission_accounts(self, mission_id: str, page: int = 1) -> Dict[str, Any]:
        """获取任务账号列表"""
        url = "http://konk.cc/tgcloud/mission/mission_account"
        
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,th;q=0.8,zh-TW;q=0.7",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Cookie": f"PHPSESSID={self.config.get('Auth', 'cookie')}",
            "Origin": "http://konk.cc",
            "Referer": "http://konk.cc/tgcloud_pc/?",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "X-KL-Ajax-Request": "Ajax_Request",
            "token": self.config.get('Auth', 'token')
        }
        
        data = {
            "map": {},
            "mission_id": mission_id,
            "page": page,
            "limit": 10
        }
        
        try:
            # 禁用SSL验证警告
            urllib3.disable_warnings()
            
            # 发送POST请求
            response = requests.post(
                url, 
                headers=headers, 
                json=data,
                verify=False
            )
            
            # 解析响应
            response_data = response.json()
            
            # 保存账号信息到数据库
            if response_data.get('code') == 1 and 'data' in response_data:
                for account in response_data['data'].get('data', []):
                    # 保存账号信息
                    account_data = {
                        'account_id': str(account.get('account_id')),
                        'phone': account.get('phone'),
                        'username': account.get('username'),
                        'has_2fa': account.get('has_2fa', False),
                        'status': account.get('status', 0)
                    }
                    self.db.save_account(account_data)
                    
                    # 保存任务账号关联
                    self.db.save_mission_account(
                        mission_id=str(mission_id),
                        account_id=str(account.get('account_id')),
                        status=account.get('status', 0)
                    )
                    
            return response_data
            
        except Exception as e:
            return {"error": str(e)}
            
    def process_request(self):
        """处理请求流程"""
        try:
            # 1. 获取任务列表
            mission_list = self.get_mission_list()
            if 'error' in mission_list:
                self.log_message.emit(f"获取任务列表失败: {mission_list['error']}")
                return
                
            if not mission_list.get('data', {}).get('data'):
                self.log_message.emit("没有找到任何任务")
                return
                
            # 2. 遍历任务列表
            total_missions = len(mission_list['data']['data'])
            
            for index, mission in enumerate(mission_list['data']['data'], 1):
                if not self.is_running:
                    break
                    
                mission_id = mission['id']
                self.log_message.emit(f"正在获取任务 {mission_id} ({index}/{total_missions}) 的账号列表")
                
                # 保存任务信息
                mission_data = {
                    'id': mission['id'],
                    'mission_type': mission.get('type'),
                    'status': mission.get('status', 0)
                }
                self.db.save_mission(mission_data)
                
                # 3. 获取任务的所有账号
                page = 1
                first_response = self.get_mission_accounts(mission_id, page)
                if 'error' in first_response:
                    self.log_message.emit(f"获取账号列表失败: {first_response['error']}")
                    continue

                # 计算总页数
                total_records = first_response['data'].get('totalPage', 0)  # 这是总记录数
                limit = first_response['data'].get('limit', 10)  # 每页条数
                total_pages = (total_records + limit - 1) // limit  # 计算实际的总页数
                
                self.log_message.emit(f"任务 {mission_id} 共有 {total_records} 条记录，每页 {limit} 条，共 {total_pages} 页")
                
                # 保存第一页数据
                if first_response.get('code') == 1 and 'data' in first_response:
                    self._save_accounts_data(first_response['data'].get('data', []), mission_id)
                
                # 获取剩余页面
                for page in range(2, total_pages + 1):
                    if not self.is_running:
                        break
                        
                    accounts = self.get_mission_accounts(mission_id, page)
                    if 'error' in accounts:
                        self.log_message.emit(f"获取第 {page} 页账号列表失败: {accounts['error']}")
                        continue
                        
                    # 保存当前页数据
                    if accounts.get('code') == 1 and 'data' in accounts:
                        self._save_accounts_data(accounts['data'].get('data', []), mission_id)
                    
                    # 更新进度
                    self.progress_updated.emit(page, total_pages)
                
                # 从数据库获取完整的任务账号列表
                mission_accounts = self.db.get_mission_accounts(mission_id)
                # 发送完整的账号列表数据
                self.request_finished.emit({
                    'code': 1,
                    'data': mission_accounts
                })
                    
        except Exception as e:
            self.log_message.emit(f"处理请求时出错: {e}")
            
    def _save_accounts_data(self, accounts: List[Dict], mission_id: str):
        """保存账号数据"""
        for account in accounts:
            # 保存账号信息
            account_data = {
                'account_id': str(account.get('account_id')),
                'phone': account.get('name', ''),  # 使用name字段作为手机号
                'username': account.get('name', ''),  # 同样使用name作为用户名
                'has_2fa': False,  # 默认值
                'status': self._convert_status(account.get('account_status', '')),  # 转换账号状态
                'success_count': account.get('msg_success_times', 0),  # 成功次数
                'fail_count': account.get('msg_error_times', 0),  # 失败次数
                'group': account.get('group_name', ''),  # 分组名称
                'two_step_password': ''  # 默认值
            }
            self.db.save_account(account_data)
            
            # 保存任务账号关联
            self.db.save_mission_account(
                mission_id=str(mission_id),
                account_id=str(account.get('account_id')),
                status=self._convert_mission_status(account.get('status', 'not_start'))
            )

    def stop(self):
        """停止处理"""
        self.is_running = False

    def setup_ui(self):
        # 设置表格基本属性
        self.tableWidget.setAlternatingRowColors(True)  # 启用隔行变色
        self.tableWidget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)  # 整行选中
        self.tableWidget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # 禁止编辑
        self.tableWidget.setShowGrid(True)  # 显示网格
        self.tableWidget.setGridStyle(Qt.PenStyle.SolidLine)  # 实线网格
        
        # 设置表格外观
        self.tableWidget.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f8f9fa;
                gridline-color: #e9ecef;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e9ecef;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #2c3e50;
            }
        """)
        
        # 优化表头
        header = self.tableWidget.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setStretchLastSection(True)  # 最后一列自适应
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # 允许手动调整列宽
        
        # 设置垂直表头
        vertical_header = self.tableWidget.verticalHeader()
        vertical_header.setDefaultSectionSize(40)  # 设置行高
        vertical_header.setVisible(False)  # 隐藏行号
        
        # 优化列宽
        self.tableWidget.setColumnWidth(0, 80)   # ID列
        self.tableWidget.setColumnWidth(1, 120)  # 账号列
        self.tableWidget.setColumnWidth(2, 120)  # 手机号列
        self.tableWidget.setColumnWidth(3, 180)  # 状态列
        
        # 启用排序
        self.tableWidget.setSortingEnabled(True)
        
        # 设置表格的选择模式
        self.tableWidget.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)  # 允许多选
        
        # 设置表格的焦点策略
        self.tableWidget.setFocusPolicy(Qt.FocusPolicy.StrongFocus) 

    def _convert_status(self, status: str) -> int:
        """转换账号状态为数字"""
        status_map = {
            'online': 0,      # 在线
            'offline': 1,     # 离线
            '': 1            # 默认在线
        }
        return status_map.get(status.lower(), 0)

    def _convert_mission_status(self, status: str) -> int:
        """转换任务状态为数字"""
        status_map = {
            'not_start': 0,   # 未开始
            'running': 1,     # 进行中
            'finished': 2,    # 已完成
            'failed': 3       # 已失败
        }
        return status_map.get(status.lower(), 0) 
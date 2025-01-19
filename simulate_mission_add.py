import requests
import urllib3
import json
from typing import Dict, Any, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal
from pathlib import Path

class MissionAddWorker(QObject):
    """Mission Add 请求处理类"""
    request_finished = pyqtSignal(dict)  # 请求完成信号
    log_message = pyqtSignal(str)  # 日志信息信号
    
    def __init__(self, config=None):
        super().__init__()
        self.is_running = True
        self.config = config
        self.account_items = ""
        self.imported_file = Path("imported_accounts.json")
        self.db = Database()  # 添加数据库实例
        
    def get_successful_accounts(self) -> List[str]:
        """从数据库中获取成功设置两步验证的账号"""
        successful_accounts = []
        try:
            # 从数据库中查询has_2fa为True的账号
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT account_id 
                    FROM accounts 
                    WHERE has_2fa = 1
                ''')
                rows = cursor.fetchall()
                successful_accounts = [str(row[0]) for row in rows]
                
            self.log_message.emit(f"从数据库中找到 {len(successful_accounts)} 个成功设置两步验证的账号")
        except Exception as e:
            self.log_message.emit(f"查询数据库时出错: {e}")
            
        return successful_accounts
        
    def load_imported_accounts(self) -> List[str]:
        """加载已导入的账号列表"""
        try:
            if self.imported_file.exists():
                with open(self.imported_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('imported_accounts', [])
            return []
        except Exception as e:
            self.log_message.emit(f"读取已导入账号记录时出错: {e}")
            return []
            
    def save_imported_accounts(self, accounts: List[str]):
        """保存已导入的账号列表"""
        try:
            # 加载现有数据
            imported_accounts = self.load_imported_accounts()
            # 添加新账号
            for account in accounts:
                if account not in imported_accounts:
                    imported_accounts.append(account)
            # 保存更新后的数据
            with open(self.imported_file, 'w', encoding='utf-8') as f:
                json.dump({'imported_accounts': imported_accounts}, f, ensure_ascii=False, indent=2)
            self.log_message.emit(f"已更新导入账号记录")
        except Exception as e:
            self.log_message.emit(f"保存导入账号记录时出错: {e}")
            
    def make_request(self, account_items: str) -> Dict:
        """发送请求"""
        url = "http://konk.cc/tgcloud/mission/mission_add"
        
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
            "type": "multi_msg",
            "account_items": account_items,
            "msg_content": "Hello",
            "msg_type": "text",
            "msg_num": 1,
            "msg_interval": 1,
            "msg_interval_type": "s",
            "msg_send_type": "order",
            "msg_send_time": 0,
            "msg_send_time_type": "s",
            "msg_send_time_start": 0,
            "msg_send_time_end": 0,
            "msg_send_time_start_type": "s",
            "msg_send_time_end_type": "s",
            "msg_send_time_interval": 0,
            "msg_send_time_interval_type": "s",
            "msg_send_time_interval_start": 0,
            "msg_send_time_interval_end": 0,
            "msg_send_time_interval_start_type": "s",
            "msg_send_time_interval_end_type": "s",
            "msg_send_time_interval_interval": 0,
            "msg_send_time_interval_interval_type": "s"
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
            return response.json()
            
        except Exception as e:
            return {"error": str(e)}
            
    def process_request(self, use_history: bool = True) -> Optional[Dict]:
        """处理请求"""
        try:
            if use_history:
                # 从数据库获取成功账号
                successful_accounts = self.get_successful_accounts()
                if not successful_accounts:
                    self.log_message.emit("没有找到成功设置两步验证的账号")
                    self.request_finished.emit({"code": 0, "msg": "没有找到成功设置两步验证的账号"})
                    return None
                    
                # 获取已导入的账号
                imported_accounts = self.load_imported_accounts()
                
                # 过滤掉已导入的账号
                unused_accounts = []
                for account in successful_accounts:
                    if account not in imported_accounts:
                        unused_accounts.append(account)
                
                if not unused_accounts:
                    self.log_message.emit("所有成功账号都已导入任务")
                    self.request_finished.emit({"code": 0, "msg": "所有成功账号都已导入任务"})
                    return None
                
                # 使用未导入的账号创建任务
                account_items = ",".join(unused_accounts)
                self.log_message.emit(f"使用未导入的成功账号创建任务: {account_items}")
            else:
                account_items = self.account_items
                self.log_message.emit(f"使用手动输入账号创建任务: {account_items}")
                
            response = self.make_request(account_items)
            
            if 'error' in response:
                self.log_message.emit(f"请求失败: {response['error']}")
            else:
                self.log_message.emit(f"请求成功: {json.dumps(response, ensure_ascii=False)}")
                # 标记账号为已导入
                self.save_imported_accounts(account_items.split(','))
                
            self.request_finished.emit(response)
            return response
            
        except Exception as e:
            error_response = {"code": 0, "msg": f"处理请求时出错: {e}"}
            self.log_message.emit(f"处理请求时出错: {e}")
            self.request_finished.emit(error_response)
            return None
            
    def stop(self):
        """停止处理"""
        self.is_running = False 
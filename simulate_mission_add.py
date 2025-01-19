import requests
import urllib3
import json
from typing import Dict, Any, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal
from pathlib import Path
from modules.database import Database  # 添加 Database 导入

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
        """发送任务添加请求"""
        url = 'http://konk.cc/tgcloud/mission/mission_add'
        
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Cookie': f"PHPSESSID={self.config.get('Auth', 'cookie')}",
            'Origin': 'http://konk.cc',
            'Referer': 'http://konk.cc/tgcloud_pc/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
            'token': self.config.get('Auth', 'token')
        }
        
        data = {
            "is_data_back_when_account_banned": 0,
            "skip_data_num": 5,
            "send_mode": "one_msg",
            "script_id": "",
            "run_together_account_num": 1,
            "data_source": "content",
            "db_id": "",
            "is_add_random_emote": 0,
            "random_emote_len": 8,
            "greating_readed_next_mode": "all",
            "nickname_source_group": "",
            "nickname_source_group_type": "text",
            "bio_source_group": "",
            "bio_source_group_type": "text",
            "avatar_source_group": "",
            "avatar_source_group_type": "text",
            "name": "555",
            "call_timeout": 0,
            "ad_type": "text",
            "reply_type": "text",
            "group_id": 44619,
            "account_type": "all",
            "account_items": account_items,
            "data_type": "phone",
            "target_data_file": "54645645645",
            "add_contacts_num_evtimes": 3,
            "phone_addcontacts_timeout_send": 60,
            "timout_after_send": 0,
            "add_contacts_times_max": 3,
            "only_active": 1,
            "send_msg_timeout": 0,
            "send_msg_max_num": 3,
            "ad_msg_content_type": "text",
            "ad_msg_content": "54645646456",
            "ad_msg_img": "",
            "is_forward_msg": 0,
            "is_need_replace_msg": 0,
            "greet_type": "edit_msg",
            "edit_delay": 0,
            "init_msg_content_type": "text",
            "init_msg_content": "",
            "is_need_reply_msg": 0,
            "reply_delay": 60,
            "reply_msg_content_type": "text",
            "reply_msg_content": "",
            "reply_msg_img": "",
            "mission_start_mode": "manual",
            "mission_start_time": "",
            "flood_error_skip_mode": "skip_account",
            "is_auto_pause_when_continuous_failed": 0,
            "continuous_failed_pause_times": 10,
            "type": "multi_msg"
        }
        
        try:
            # 禁用 SSL 警告
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = requests.post(
                url,
                headers=headers,
                json=data,
                verify=False  # 对应 curl 的 --insecure 参数
            )
            
            return response.json()
        except Exception as e:
            self.log_message.emit(f"请求发送失败: {str(e)}")
            return {"code": -1, "msg": str(e)}
            
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
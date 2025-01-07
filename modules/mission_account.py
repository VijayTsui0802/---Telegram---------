import requests
import urllib3
import json
from typing import Dict, Any, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal
from pathlib import Path

class MissionAccountWorker(QObject):
    """Mission Account 请求处理类"""
    request_finished = pyqtSignal(dict)  # 请求完成信号
    log_message = pyqtSignal(str)  # 日志信息信号
    progress_updated = pyqtSignal(int, int)  # 进度更新信号
    
    def __init__(self, config=None):
        super().__init__()
        self.is_running = True
        self.config = config
        self.data_file = Path("mission_accounts.json")
        self.saved_data = self.load_saved_data()
        
    def load_saved_data(self) -> Dict:
        """加载已保存的数据"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.log_message.emit(f"加载保存数据失败: {e}")
            return {}
            
    def save_data(self, mission_id: int, accounts_data: Dict):
        """保存任务账号数据"""
        try:
            self.saved_data[str(mission_id)] = accounts_data
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_data, f, ensure_ascii=False, indent=2)
            self.log_message.emit(f"已保存任务 {mission_id} 的账号数据")
        except Exception as e:
            self.log_message.emit(f"保存数据失败: {e}")
            
    def get_saved_accounts(self, mission_id: int) -> Optional[Dict]:
        """获取已保存的账号数据"""
        return self.saved_data.get(str(mission_id))

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
            "map": {"type": "filter"},
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
            return response_data
            
        except Exception as e:
            return {"error": str(e)}
            
    def get_mission_accounts(self, mission_id: int, page: int = 1) -> Dict[str, Any]:
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
            # 发送POST请求
            response = requests.post(
                url, 
                headers=headers, 
                json=data,
                verify=False
            )
            
            # 解析响应
            response_data = response.json()
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
            for mission in mission_list['data']['data']:
                if not self.is_running:
                    break
                    
                mission_id = mission['id']
                
                # 检查是否已有保存的数据
                saved_accounts = self.get_saved_accounts(mission_id)
                if saved_accounts:
                    self.log_message.emit(f"使用已保存的任务 {mission_id} 账号数据")
                    self.request_finished.emit(saved_accounts)
                    continue
                
                self.log_message.emit(f"正在获取任务 {mission_id} 的账号列表")
                
                # 3. 获取任务的所有账号
                page = 1
                first_response = self.get_mission_accounts(mission_id, page)
                if 'error' in first_response:
                    self.log_message.emit(f"获取账号列表失败: {first_response['error']}")
                    continue

                # 计算总页数
                total_records = first_response['data']['totalPage']  # 这是总记录数
                limit = first_response['data']['limit']  # 每页条数
                total_pages = (total_records + limit - 1) // limit  # 计算总页数
                
                self.log_message.emit(f"任务 {mission_id} 共有 {total_records} 条记录，每页 {limit} 条，共 {total_pages} 页")
                
                # 收集所有页面的数据
                all_accounts_data = first_response
                all_accounts_data['data']['data'] = []  # 清空数据列表，准备收集所有页面的数据
                
                # 获取所有页面
                for page in range(1, total_pages + 1):
                    if not self.is_running:
                        break
                        
                    accounts = self.get_mission_accounts(mission_id, page)
                    if 'error' in accounts:
                        self.log_message.emit(f"获取第 {page} 页账号列表失败: {accounts['error']}")
                        continue
                        
                    # 添加当前页的数据
                    all_accounts_data['data']['data'].extend(accounts['data']['data'])
                    
                    # 更新进度
                    self.progress_updated.emit(page, total_pages)
                
                # 保存完整数据
                self.save_data(mission_id, all_accounts_data)
                
                # 发送完整数据
                self.request_finished.emit(all_accounts_data)
                    
        except Exception as e:
            self.log_message.emit(f"处理请求时出错: {e}")
            
    def stop(self):
        """停止处理"""
        self.is_running = False 
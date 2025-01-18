import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

class Database:
    """数据库管理类"""
    def __init__(self, db_path: str = "data.db"):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建accounts表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY,
                    account_id TEXT NOT NULL UNIQUE,
                    phone TEXT,
                    username TEXT,
                    has_2fa BOOLEAN,
                    status INTEGER,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            ''')

            # 创建missions表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS missions (
                    id INTEGER PRIMARY KEY,
                    mission_id TEXT NOT NULL UNIQUE,
                    mission_type TEXT,
                    status INTEGER,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            ''')

            # 创建mission_accounts表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mission_accounts (
                    id INTEGER PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    status INTEGER,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE(mission_id, account_id)
                )
            ''')

            # 创建verification_codes表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS verification_codes (
                    id INTEGER PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    send_time INTEGER,
                    created_at TIMESTAMP
                )
            ''')

            # 创建configs表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configs (
                    id INTEGER PRIMARY KEY,
                    key TEXT NOT NULL UNIQUE,
                    value TEXT,
                    updated_at TIMESTAMP
                )
            ''')

            conn.commit()

    def save_account(self, account_data: Dict[str, Any]):
        """保存账号信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT OR REPLACE INTO accounts 
                (account_id, phone, username, has_2fa, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM accounts WHERE account_id = ?), ?), ?)
            ''', (
                str(account_data.get('account_id')),
                account_data.get('phone'),
                account_data.get('username'),
                account_data.get('has_2fa', False),
                account_data.get('status', 0),
                str(account_data.get('account_id')),
                now,
                now
            ))

    def save_mission(self, mission_data: Dict[str, Any]):
        """保存任务信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT OR REPLACE INTO missions 
                (mission_id, mission_type, status, created_at, updated_at)
                VALUES (?, ?, ?, COALESCE((SELECT created_at FROM missions WHERE mission_id = ?), ?), ?)
            ''', (
                str(mission_data.get('id')),
                mission_data.get('type'),
                mission_data.get('status', 0),
                str(mission_data.get('id')),
                now,
                now
            ))

    def save_mission_account(self, mission_id: str, account_id: str, status: int = 0):
        """保存任务账号关联"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT OR REPLACE INTO mission_accounts 
                (mission_id, account_id, status, created_at, updated_at)
                VALUES (?, ?, ?, COALESCE((SELECT created_at FROM mission_accounts WHERE mission_id = ? AND account_id = ?), ?), ?)
            ''', (
                str(mission_id),
                str(account_id),
                status,
                str(mission_id),
                str(account_id),
                now,
                now
            ))

    def save_verification_code(self, account_id: str, code: str, send_time: int):
        """保存验证码信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT INTO verification_codes 
                (account_id, code, send_time, created_at)
                VALUES (?, ?, ?, ?)
            ''', (
                str(account_id),
                code,
                send_time,
                now
            ))

    def save_config(self, key: str, value: Any):
        """保存配置信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT OR REPLACE INTO configs 
                (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (
                key,
                json.dumps(value) if isinstance(value, (dict, list)) else str(value),
                now
            ))

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """获取账号信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM accounts WHERE account_id = ?', (str(account_id),))
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'account_id': row[1],
                    'phone': row[2],
                    'username': row[3],
                    'has_2fa': bool(row[4]),
                    'status': row[5],
                    'created_at': row[6],
                    'updated_at': row[7]
                }
            return None

    def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM missions WHERE mission_id = ?', (str(mission_id),))
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'mission_id': row[1],
                    'mission_type': row[2],
                    'status': row[3],
                    'created_at': row[4],
                    'updated_at': row[5]
                }
            return None

    def get_mission_accounts(self, mission_id: str, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        """获取任务的账号列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取总记录数
            cursor.execute('''
                SELECT COUNT(*) 
                FROM mission_accounts ma 
                JOIN accounts a ON ma.account_id = a.account_id 
                WHERE ma.mission_id = ?
            ''', (str(mission_id),))
            total = cursor.fetchone()[0]
            
            # 获取分页数据
            cursor.execute('''
                SELECT a.* 
                FROM mission_accounts ma 
                JOIN accounts a ON ma.account_id = a.account_id 
                WHERE ma.mission_id = ?
                LIMIT ? OFFSET ?
            ''', (str(mission_id), limit, (page - 1) * limit))
            
            rows = cursor.fetchall()
            accounts = []
            for row in rows:
                accounts.append({
                    'id': row[0],
                    'account_id': row[1],
                    'phone': row[2],
                    'username': row[3],
                    'has_2fa': bool(row[4]),
                    'status': row[5],
                    'created_at': row[6],
                    'updated_at': row[7]
                })
            
            return {
                'total': total,
                'page': page,
                'limit': limit,
                'data': accounts
            }

    def get_latest_verification_code(self, account_id: str) -> Optional[Dict[str, Any]]:
        """获取最新的验证码信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM verification_codes 
                WHERE account_id = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            ''', (str(account_id),))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'account_id': row[1],
                    'code': row[2],
                    'send_time': row[3],
                    'created_at': row[4]
                }
            return None

    def get_config(self, key: str) -> Any:
        """获取配置信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM configs WHERE key = ?', (key,))
            row = cursor.fetchone()
            
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return row[0]
            return None

    def migrate_from_json(self, history_file: str):
        """从JSON文件迁移数据到数据库"""
        if not Path(history_file).exists():
            return
            
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
                
            for account_id, data in history_data.items():
                account_data = {
                    'account_id': account_id,
                    'has_2fa': data.get('has_2fa', False),
                    'status': 1 if data.get('imported_to_mission') else 0
                }
                self.save_account(account_data)
                
                if 'result' in data:
                    result = data['result']
                    if isinstance(result, dict) and 'code' in result:
                        self.save_verification_code(
                            account_id,
                            result['code'],
                            data.get('request_time', 0)
                        )
        except Exception as e:
            print(f"数据迁移失败: {e}") 
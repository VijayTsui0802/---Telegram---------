import requests
import time
from typing import Dict, Any
import json

def make_request(id: int) -> Dict[str, Any]:
    """发送单个请求并返回响应"""
    url = f"http://konk.cc/tgcloud/account/account_mission"
    
    # 请求头设置
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,th;q=0.8,zh-TW;q=0.7",
        "Connection": "keep-alive",
        "Cookie": "PHPSESSID=8j6pbauibgdufnbgduijtafes7",
        "Referer": "http://konk.cc/tgcloud_pc/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "X-KL-Ajax-Request": "Ajax_Request",
        "token": "2541343f-0c02-44df-9c8a-f6066dbbc8b1"
    }
    
    # 请求参数
    params = {
        "id": id,
        "page": 1,
        "limit": 100
    }
    
    try:
        # 发送请求，禁用SSL验证
        response = requests.get(url, headers=headers, params=params, verify=False)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def main():
    # 设置起始ID和结束ID
    start_id = 12665581
    end_id = 12665581
    
    # 禁用请求的SSL警告
    requests.packages.urllib3.disable_warnings()
    
    print("开始发送请求...")
    print("-" * 50)
    
    for id in range(start_id, end_id + 1):
        print(f"正在请求 ID: {id}")
        response = make_request(id)
        
        # 格式化输出响应
        print(f"响应结果: {json.dumps(response, ensure_ascii=False, indent=2)}")
        print("-" * 50)
        
        # 添加延时，避免请求过于频繁
        time.sleep(1)

if __name__ == "__main__":
    main() 
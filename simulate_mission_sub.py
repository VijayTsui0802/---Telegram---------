import requests
import json
import urllib3
import os
import time
from typing import Dict, Any, List

def load_successful_mission_ids() -> List[str]:
    """从request_history.json加载成功设置两步密码的mission_id"""
    try:
        with open('request_history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
            
        successful_ids = []
        for mission_id, data in history.items():
            if "设置两步密码" in data.get("result", ""):
                successful_ids.append(mission_id)
                
        return successful_ids
    except Exception as e:
        print(f"读取历史记录失败: {e}")
        return []

def make_request(mission_id: int) -> Dict[str, Any]:
    """发送mission_sub_list请求并返回响应"""
    url = "http://konk.cc/tgcloud/mission/mission_sub_list"
    
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,th;q=0.8,zh-TW;q=0.7",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Cookie": "PHPSESSID=p3q7fib4o55k9frm9p3qu32qd9",
        "Origin": "http://konk.cc",
        "Referer": "http://konk.cc/tgcloud_pc/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "X-KL-Ajax-Request": "Ajax_Request",
        "token": "2541343f-0c02-44df-9c8a-f6066dbbc8b1"
    }
    
    data = {
        "mission_id": mission_id,
        "page": 1,
        "limit": 10,
        "map": {
            "status": "",
            "name": ""
        }
    }
    
    try:
        # 禁用SSL验证警告
        urllib3.disable_warnings()
        
        # 发送POST请求
        response = requests.post(
            url, 
            headers=headers, 
            json=data,
            verify=False  # 禁用SSL验证
        )
        
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def main():
    print("TG Cloud Mission Sub List 自动请求工具")
    print("-" * 50)
    
    # 加载成功的mission_id列表
    successful_ids = load_successful_mission_ids()
    if not successful_ids:
        print("没有找到成功的mission_id记录")
        return
        
    print(f"找到 {len(successful_ids)} 个成功的mission_id")
    print("开始自动请求...")
    print("-" * 50)
    
    # 创建结果目录
    if not os.path.exists('results'):
        os.makedirs('results')
    
    # 记录开始时间
    start_time = time.time()
    
    # 循环处理每个mission_id
    for idx, mission_id in enumerate(successful_ids, 1):
        try:
            print(f"\n[{idx}/{len(successful_ids)}] 正在请求 mission_id: {mission_id}")
            response = make_request(int(mission_id))
            
            # 保存响应到文件
            result_file = f'results/mission_{mission_id}.json'
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(response, f, ensure_ascii=False, indent=2)
            
            print(f"响应已保存到: {result_file}")
            
            # 简单显示响应状态
            if "error" in response:
                print(f"请求失败: {response['error']}")
            else:
                print("请求成功")
            
            # 添加延时，避免请求过快
            time.sleep(1)
            
        except Exception as e:
            print(f"处理mission_id {mission_id}时出错: {e}")
            continue
    
    # 记录结束时间和总用时
    end_time = time.time()
    total_time = end_time - start_time
    
    print("\n" + "=" * 50)
    print(f"任务完成!")
    print(f"总共处理: {len(successful_ids)} 个mission_id")
    print(f"总用时: {total_time:.2f} 秒")
    print("结果已保存到 results 目录")
    print("=" * 50)

if __name__ == "__main__":
    main() 
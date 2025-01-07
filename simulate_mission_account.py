import requests
import json
import urllib3
import time
import os
from typing import Dict, Any, Tuple

def parse_range(range_str: str) -> Tuple[int, int]:
    """解析用户输入的范围
    格式: start-end, 例如: 1599867-1599869
    """
    try:
        start, end = map(int, range_str.split('-'))
        if start > end:
            start, end = end, start
        return start, end
    except:
        raise ValueError("请输入正确的范围格式，例如: 1599867-1599869")

def make_request(mission_id: int) -> Dict[str, Any]:
    """发送mission_account请求并返回响应"""
    url = "http://konk.cc/tgcloud/mission/mission_account"
    
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,th;q=0.8,zh-TW;q=0.7",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Cookie": "PHPSESSID=p3q7fib4o55k9frm9p3qu32qd9",
        "Origin": "http://konk.cc",
        "Referer": "http://konk.cc/tgcloud_pc/?",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "X-KL-Ajax-Request": "Ajax_Request",
        "token": "468e5374-8853-456c-a9e7-9eacdd4cdcde"
    }
    
    data = {
        "map": {},
        "mission_id": mission_id,
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
            verify=False  # 禁用SSL验证
        )
        
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def process_range(start_id: int, end_id: int):
    """处理一个范围内的所有mission_id"""
    # 创建结果目录
    if not os.path.exists('results'):
        os.makedirs('results')
    
    total = end_id - start_id + 1
    start_time = time.time()
    
    print(f"\n开始处理范围: {start_id} - {end_id}")
    print(f"总共需要处理: {total} 个mission_id")
    print("-" * 50)
    
    for idx, mission_id in enumerate(range(start_id, end_id + 1), 1):
        try:
            print(f"\n[{idx}/{total}] 正在请求 mission_id: {mission_id}")
            response = make_request(mission_id)
            
            # 保存响应到文件
            result_file = f'results/mission_account_{mission_id}.json'
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(response, f, ensure_ascii=False, indent=2)
            
            print(f"响应已保存到: {result_file}")
            
            # 显示响应状态
            if "error" in response:
                print(f"请求失败: {response['error']}")
            else:
                print("请求成功")
            
            # 添加延时，避免请求过快
            time.sleep(1)
            
        except Exception as e:
            print(f"处理mission_id {mission_id}时出错: {e}")
            continue
    
    # 统计信息
    end_time = time.time()
    total_time = end_time - start_time
    print("\n" + "=" * 50)
    print(f"范围处理完成!")
    print(f"处理范围: {start_id} - {end_id}")
    print(f"总共处理: {total} 个mission_id")
    print(f"总用时: {total_time:.2f} 秒")
    print("结果已保存到 results 目录")
    print("=" * 50)

def main():
    print("TG Cloud Mission Account 请求模拟器")
    print("-" * 50)
    print("支持以下输入格式:")
    print("1. 单个mission_id")
    print("2. ID范围 (例如: 1599867-1599869)")
    print("输入'q'退出程序")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("\n请输入mission_id或范围: ").strip()
            
            if user_input.lower() == 'q':
                print("\n程序已退出")
                break
            
            if '-' in user_input:
                # 处理范围
                start_id, end_id = parse_range(user_input)
                process_range(start_id, end_id)
            else:
                # 处理单个ID
                mission_id = int(user_input)
                print(f"\n正在请求 mission_id: {mission_id}")
                response = make_request(mission_id)
                print("\n响应结果:")
                print(json.dumps(response, ensure_ascii=False, indent=2))
                print("-" * 50)
            
        except ValueError as e:
            print(f"输入错误: {e}")
        except KeyboardInterrupt:
            print("\n程序已终止")
            break
        except Exception as e:
            print(f"发生错误: {e}")

if __name__ == "__main__":
    main() 
# 控客-Telegram云控系统-账号提取

## 版本历史

### v1.1.0 (2024-01-13)
- 优化在线接码页面的任务获取逻辑
  - 修改为先获取任务列表，再获取每个任务的账号
  - 修复了任务总数显示错误的问题
  - 优化了分页逻辑计算
- 改进UI交互
  - 修复了按钮状态管理问题
  - 在获取验证码时禁用其他按钮
  - 优化了进度显示和日志输出
- 数据处理优化
  - 修正了数据字段映射
  - 优化了验证码获取和显示逻辑
  - 改进了数据缓存管理

## 功能特性
- 支持多任务批量获取账号信息
- 实时获取验证码功能
- 支持账号状态和任务状态的可视化显示
- 提供数据分页和搜索功能
- 支持双击复制账号信息
- 完整的日志记录系统

## 安装说明
1. 确保已安装Python 3.8+
2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法
1. 配置config.ini文件，填入必要的认证信息
2. 运行主程序：
```bash
python gui_main.py
```

## 注意事项
- 使用前请确保config.ini中的认证信息正确
- 建议定期清理缓存数据
- 获取验证码时请勿频繁操作，建议等待系统自动刷新 

## 版本更新步骤
1. 更新代码和文档
   - 修改相关代码文件
   - 更新 README.md 中的版本历史
   - 更新 requirements.txt（如有依赖变更）

2. 提交更改
   ```bash
   git add .
   git commit -m "vX.X.X 版本更新：更新内容描述"
   ```

3. 创建版本标签
   ```bash
   git tag -a vX.X.X -m "版本X.X.X发布：版本说明"
   ```

4. 推送到远程仓库
   ```bash
   git push origin main
   git push origin vX.X.X
   ```

5. 确认更新
   - 在 GitHub 仓库检查代码更新
   - 确认版本标签创建成功
   - 检查文档更新是否正确 

git tag v1.2.4    
git push origin v1.2.4


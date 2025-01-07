# TG Cloud 请求模拟器

基于 PyQt6 的请求模拟工具，用于模拟 TG Cloud 的 API 请求。

## 环境要求

- Python 3.8+
- Poetry

## 安装

1. 安装 Poetry（如果未安装）:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. 安装项目依赖:
```bash
poetry install
```

## 运行

```bash
poetry run python gui_main.py
```

或者先激活虚拟环境后运行：
```bash
# 激活虚拟环境
poetry shell

# 运行程序
python gui_main.py
```

## 开发

1. 激活虚拟环境:
```bash
poetry shell
```

2. 添加新依赖:
```bash
poetry add package-name
```

## 项目结构

```
tgcloud-request-simulator/
├── gui_main.py          # 主程序
├── pyproject.toml       # Poetry 配置文件
└── README.md           # 项目说明文档
``` 
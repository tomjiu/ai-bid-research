# AI 智能标书系统

基于 AI 的投标文件辅助生成系统，支持招标文件解析、章节内容智能生成、废标风险检查及 Word 格式导出。

## 功能概览

- 招标文件上传与解析（PDF / Word）
- 自动生成投标文件目录结构
- AI 逐章节生成投标内容（流式输出）
- 废标风险检查
- 一键导出标准格式 Word 投标文件

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + Element Plus + TypeScript |
| 后端 | Python 3.11+ / Flask 3 / SQLAlchemy / SQLite |
| AI 工作流 | [Dify](https://github.com/langgenius/dify/)（自部署）|
| 文档生成 | python-docx |

## 快速启动

### 前提条件

- Python ≥ 3.11
- Node.js ≥ 20.19 或 ≥ 22.12
- 已部署 Dify 实例并创建三个工作流（见 [Dify 工作流配置](#dify-工作流配置)）

### 1. 克隆仓库

```bash
git clone https://github.com/Chengyihaowen/llm_bidwriting.git
cd 标书系统v3.0
```

### 2. 启动后端

```bash
cd backend
cp .env.example .env      # 填写环境变量
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install uv && uv sync
python app.py
```

后端默认监听 `http://localhost:5000`。

### 3. 启动前端

```bash
cd frontend
cp .env.example .env      # 填写 VITE_API_BASE_URL
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`。

## 环境变量说明

### backend/.env

```dotenv
# Flask
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=<自定义随机字符串>

# 数据库（默认 SQLite，无需修改）
DATABASE_URL=sqlite:///bid_system.db

# 文件存储
UPLOAD_FOLDER=./uploads
MAX_CONTENT_LENGTH=52428800   # 50 MB

# Dify 配置（必填）
DIFY_BASE_URL=http://<your-dify-host>/v1
DIFY_API_KEY_PARSE=app-<招标文件解析工作流 Key>
DIFY_API_KEY_GENERATE=app-<章节生成工作流 Key>
DIFY_API_KEY_CHECK=app-<废标检查工作流 Key>
```

### frontend/.env

```dotenv
VITE_API_BASE_URL=http://localhost:5000
```

## Dify 工作流配置

本项目依赖三个 Dify 工作流，可直接导入 `docs/dify_constronstor/` 下的 YAML 文件：

| 文件 | 用途 |
|---|---|
| `招标文件解析工作流.yml` | 解析上传的招标文件，提取关键信息与目录结构 |
| `章节生成工作流.yml` | 根据章节要求逐节生成投标内容 |
| `废标检查工作流.yml` | 检查投标文件是否存在废标风险 |

**Dify 官网**：[https://github.com/langgenius/dify/](https://github.com/langgenius/dify/) — 支持云端使用或自部署，参考官方文档完成环境搭建后，在「工作流」页面点击「导入」即可加载上述 YAML 文件。

## 文档

`docs/spec/` 目录包含完整的项目设计文档：

| 文件 | 内容 |
|---|---|
| `01-product-overview.md` | 产品概述 |
| `02-prd.md` | 需求规格 |
| `03-functional-spec.md` | 功能详细说明 |
| `04-architecture.md` | 架构设计 |
| `05-api-data-model.md` | API 与数据模型 |
| `06-Dify通用投标文件生成工作流.md` | Dify 工作流设计 |
| `07-word-export-spec.md` | Word 导出规范 |
| `09-dify-workflow-split-design.md` | 工作流拆分设计 |
| `10-dify-node-config-prompts-backend-mapping.md` | 节点配置与提示词映射 |
| `dify工作流以及提示词.md` | 工作流提示词详情 |

## 项目结构

```
.
├── backend/               # Flask 后端
│   ├── app.py             # 应用入口
│   ├── config.py          # 配置
│   ├── models.py          # 数据模型
│   ├── routes/            # 路由（projects / generation / export / knowledge）
│   └── utils/             # Dify 客户端、知识库工具等
├── frontend/              # Vue 3 前端
│   └── src/
│       ├── views/         # 页面
│       ├── components/    # 组件
│       └── api/           # 接口封装
└── docs/
    ├── spec/              # 设计文档
    └── dify_constronstor/ # Dify 工作流 YAML（可直接导入）
```

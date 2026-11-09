# Tender Master · 招投标编制专家 Skill + Agent

一个可供 coding agent（Claude Code / Codex / Cursor / OpenClaw 等）调用的**标准化招投标编制** skill 与智能体，由四个成熟招投标项目融合而成，取各家所长：

| 来源能力 | 本 skill 承接位置 |
| --- | --- |
| 九步流程管控 + 权限红线 + 风控/正文物理隔离 | 主流程骨架、步骤①④⑤ |
| 标的四模式分类 + 厚标书规则 + 五专家评审 + 无依赖质检脚本 | 步骤①.5⑤⑦、`bid_quality_check.py` |
| 评审表驱动 + 评分镜像目录 + docx 排版规范 | 步骤③⑧、`chapter-writing`/`outline`/`style-guide` |
| 行业自动检测 + 字数公式 + AI 去痕 + 文档转换工具链 | 步骤①.5、`industry-guides`、`convert_to_md`/`check_word_count` |

## 核心理念

1. **目录 = 评分表镜像** —— 评委翻目录就能逐项对上得分点；
2. **每条要求逐条响应** —— 技术响应表 T-NNN 贯穿目录→提示词→正文，不断链；
3. **风控与正文物理隔离** —— 分值/废标条款绝不进正文；
4. **不编造** —— 资质/案例/参数/人员用占位符或引用附件；
5. **标的模式控制厚度** —— 货物类薄而准，软件平台类厚而实，服务类重人/流程/记录。

## 九步流程

```
① 招标解析 → ①.5 标的模式判定 → ② 三份基准表 → ③ 评分镜像目录
④ 提示词+风控台账 → ⑤ 逐章撰写 → ⑥ 全文合并 → ⑦ 质检+五专家评审
⑧ 标准化排版 → ⑨ 归档闭环
```
每步产出独立文件，用户 `确认通过` 后进入下一步。

## 目录结构

```
tender-master/
├── SKILL.md                        # 主入口：角色、九步流程、权限红线、资源索引
├── README.md
├── agents/
│   ├── tender-agent.md             # 供 coding agent 调用的子代理定义（调用契约+准则）
│   └── openai.yaml                 # Codex/OpenAI UI 元数据
├── references/                     # 按需懒加载
│   ├── parsing-rules.md            # ① 清洗与三分法
│   ├── bid-type-modes.md           # ①.5 四模式判定与规则
│   ├── industry-guides.md          # 8 行业侧重
│   ├── checklists.md               # 三表模板/需求台账/质检卡/五专家评分卡
│   ├── outline-generation.md       # ③ 目录骨架与映射
│   ├── prompt-and-riskledger.md    # ④ 提示词与风控台账字段模板
│   ├── thick-proposal-rules.md     # ⑤ 厚标书规则
│   ├── chapter-writing.md          # ⑤ 各类章节写法与降 AI 味
│   ├── business-bid.md             # 商务标/资信标/商务偏离/资格审查
│   ├── engineering-bid.md          # 工程咨询/监测/测绘专用（16章格式/影响分区/2002报价）
│   ├── style-guide.md              # ⑧ 中文标书 docx 排版规范
│   ├── workflow.md                 # 全流程/阶段门禁/异常处理
│   └── platform-compatibility.md   # 移植到 Codex/OpenClaw/Hermes/Cursor
└── scripts/                        # 可选，缺依赖可退化为手动清单
    ├── convert_to_md.py            # 招标文件 → Markdown
    ├── extract_scoring.py          # 评分标准启发式提取 → JSON
    ├── extract_requirements.py     # 资质/技术/商务/废标要求提取 → JSON
    ├── check_word_count.py         # 按分值比例检查字数
    ├── bid_quality_check.py        # 无依赖确定性质检（占位符/覆盖/证据）
    ├── monitoring_fee_estimate.py   # 工程监测报价估算（2002标准：点次/米次→技术费→折扣）
    ├── build_docx.py                # 单份标书 Markdown → DOCX（跨平台/政企公路格式预设）
    └── build_bid_package.py         # 一键整合：多章节+（可选）报价明细 → 单个投标 DOCX
└── examples/                       # 两个端到端可运行样例（均含 00~06 产物与整合 DOCX）
    ├── 地铁保护区第三方监测示例/    # 工程监测（地保）：监测16章/影响分区分级/报警值/应急
    └── 城市地形测绘样例/            # 工程测绘：测绘12章骨架/三级检查/商务标（投标函+偏离表+资格对照）
```

样例说明见 [`examples/README.md`](examples/README.md)。

## 安装

**Claude Code**：把整个 `tender-master/` 目录放入
```
~/.claude/skills/tender-master/
```
在会话中说：`使用 tender-master 帮我编制这个项目的技术标，招标文件：./招标文件.pdf`

**Codex / Cursor / OpenClaw**：把目录放入对应 skills 路径，或直接让 agent 读取 `SKILL.md`。作为子代理时读取 `agents/tender-agent.md`。移植细则见 `references/platform-compatibility.md`。

## 快速开始

```
请阅读 SKILL.md，理解角色定位、九步流程与权限红线，然后告诉我你已准备好。
执行步骤1：解析招标文件，项目名：XX智慧交通项目，招标文件路径：./00_source/招标文件.pdf
```
随后按 `确认通过` / `目录确认通过` / `本章定稿` / `驳回重做：原因` / `整改完成` 逐步推进。

## 依赖（脚本可选）

```bash
pip install pdfplumber python-docx   # convert_to_md.py(pdf/docx)、build_docx.py 需要 python-docx
# bid_quality_check.py / extract_*.py / check_word_count.py / monitoring_fee_estimate.py 无第三方依赖
# build_docx.py 可选 --engine pandoc（需系统安装 pandoc）
```
若环境不能跑脚本，本 skill 仍可通过阅读文档、手动产出台账/评审正常工作。

## 覆盖范围

- **技术标**（主线，九步流程全覆盖）
- **商务标/资信标**（`references/business-bid.md`：投标函、资格审查对照、商务偏离表、业绩团队证据、商务质检）
- **价格/报价**：由人工核定；工程监测类可用 `monitoring_fee_estimate.py`（2002 收费标准）辅助估算
- **工程技术咨询/监测/测绘专用流程**（`references/engineering-bid.md`：轨道交通第三方监测/地保监测/基坑隘道监测，监测标 16 章标准格式、影响分区分级、数据闭环、报警值、应急预案、监测专家评审；**工程测量测绘标专属章节骨架**（通用测绘/变形测量两套）；品牌隔离）

纯施工类的施工组织设计、工程量清单、施工进度需另配施工标流程。

## License

MIT（沿用来源项目许可）。

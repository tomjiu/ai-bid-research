# 用户手册——ai-bid-research 标书系统

> 面向使用者：怎么从一份招标文件，走到一份能递交的投标文件。
> 开发者文档见 `docs/`（架构决策 / 契约 / 模型）；本手册只讲操作。

---

## 一、系统做什么

```
招标文件（docx / pdf / xlsx）          你的证据（资质 / 业绩 / 证书）
        │                                       │
        ▼                                       ▼
   ① 导入 + 解析                        证据台账登记
        │                                       │
        ▼                                       │
   ② 条款抽取（资格/否决/评分/参数/商务/格式）    │
        │                                       │
        ▼                                       ▼
   ③ 响应矩阵（要求 × 证据绑定 × 响应状态）◄──────┘
        │
        ▼
   ④ 章节树 + 字数配额（大纲）
        │
        ▼
   ⑤ 逐章起草（AI 生成 / mock；引用回查防幻觉）
        │
        ▼
   ⑥ 校验（8 条确定性规则——防废标最后一道关）
        │
        ▼
   ⑦ 导出（docx / pdf；格式从招标文件提取——不硬编码；暗标脱敏）
```

**三个安全闸门**（缺一不可，全部通过才能导出）：

1. **矩阵门**：每条必选条款（资格/否决）都有响应（证据绑定或人工覆写）；
2. **审核门**：三道人工审核门过审（矩阵定稿 → 大纲定稿 → 导出前确认——
   审核人必须 `human:` 前缀，AI 不得自审自过）；
3. **校验门**：`validate_bid_document` 的 BLOCKER 清零（未响应否决项 /
   空章节 / 幻觉引用 / 失效证据——任何一条都是废标级风险）。

---

## 二、启动桌面壳（Windows）

```bat
:: 编译需要先跑 vcvars（否则报 link.exe not found）
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
cd /d E:\Code\ai\md\audit\ai-bid-research\bidcore
cargo run -p mang-app
```

桌面壳是 VSCode 风格的标书工作台：左侧文件树 / 中间编辑区 / 右侧面板；
带版本历史（自动快照 + AI 存版徽章）、来源标注浮层（点角标看条款原文）、
文档大纲面板（1330 页标书的导航刚需）。

---

## 三、跑一次完整流程（命令行 e2e）

```bash
# 一条命令：招标文件进 → 成品标书出（corpus-A 真件演示）
./scripts/e2e_bid/run_e2e.sh
```

跑的是什么（8 步，每步失败会定位到步号）：

| 步 | 做什么 | 产物在哪 |
|---|---|---|
| ① | 建项目 | 工作区 `db.json` |
| ② | 导入招标文件 + 证据 | 解析统计（页/块/表） |
| ③ | 抽取条款 | REQ 台账（六类分类） |
| ④ | 建大纲 + 矩阵 | 章节树（字数配额） |
| ⑤ | 绑证据 + 三道审核门 | 矩阵响应状态 |
| ⑥ | 逐章起草 | `chapters/*.json`（断点续跑） |
| ⑦ | 校验 | BLOCKER 清零报告 |
| ⑧ | 导出 | `out/投标文件-技术标.docx` |

**中途崩了怎么办**：直接重跑。断点续跑是结构保证——已完成的章一个字节
不重写、不重复生成（token 不浪费）。

---

## 四、MCP 工具面（AI Agent 调用）

**44 个工具**（`bid-mcp-stdio` 的 stdio 协议 / `bid-mcp-server` 的标准 MCP 传输），按项目状态机有序开放。工具契约单一真源 = `docs/bid-mcp-contract.md`；发现面 = `list_tools` 工具或 MCP `tools/list`。按产品域分组：

**核心链（P0→P8 主线）**

| 工具 | 什么时候能调 | 干什么 |
|---|---|---|
| `create_bid_project` | 起步 | 建项目（external_key 幂等——重复调不重复建） |
| `import_tender_files` | 建项后 | 导入文件（sha256 幂等——同文件重导去重；完整性对账） |
| `extract_requirements` | 导入后 | 抽条款（六类；重抽零新增——幂等合并） |
| `build_outline` | 抽取后 | 建纲 + 矩阵首建（#287 篇幅档位四选一，见 `recommend_length_profile`） |
| `draft_response_section` | 矩阵就绪后 | 单章起草（`generator: auto\|mock\|real\|external`——external = Skill 驱动 Agent 写正文的标准模式；引用回查防幻觉；字数带宽；未回应条款即时告警） |
| `validate_bid_document` | 起草后 | 校验（确定性规则 + 模型复核——BLOCKER 清零才可导出） |
| `export_bid_document` | 校验+审校后 | 导出（docx/pdf；暗标模式；sha256 落库，中断不留半成品） |
| `save_version` | 随时 | 存版本快照（桌面壳「改动」面板可见） |

**只读对账（断点恢复与核对）**

| 工具 | 什么时候能调 | 干什么 |
|---|---|---|
| `get_bid_project_state` | 随时 | 看状态 + 下一步允许哪些工具（断点恢复入口——含 DIRTY 章节清单） |
| `get_compliance_matrix` | 随时 | 看矩阵（要求×响应状态，游标分页） |
| `list_evidence` / `list_tasks` | 随时 | 证据台账 / 任务分工（过滤 + 游标分页） |
| `search_evidence` | 随时 | 双通道证据检索（exact 五字段 / semantic 正文摘录） |
| `check_bid_quality` | 矩阵就绪后 | 质量体检（覆盖度/幻觉引用/字数带宽/全局一致性——报告落 `artifacts/quality-report.json`） |
| `list_tools` | 建项目前即可 | 行协议握手发现面（工具清单 + 契约摘要） |
| `recommend_length_profile` | 抽取后 | 篇幅档位推荐（P3 建纲**前**调——决策权在用户） |
| `get_coverage_report` | 随时 | 覆盖报告（哪些块没归属——全覆盖才允许建纲） |
| `get_star_coverage` | 导入后 | ★漏标检测（字面★真值 vs 已抽 REQ 差集） |
| `get_requirement_provenance` | 随时 | REQ→原文溯源（锚点带 block_idx/page/line） |
| `get_block_requirements` | 随时 | 块→REQ 反查（原文 + verdict；无 REQ 块照常返回） |
| `get_annotation_overlay` | 随时 | 视图层 overlay 数据面（渲染上色用，含 suspected_miss） |

**块标记（导入后~建纲前的标记窗口）**

| 工具 | 什么时候能调 | 干什么 |
|---|---|---|
| `get_document_chunks` | 导入后~建纲前 | 按文件取块窗口（block_idx + text + verdict 回显） |
| `submit_block_marks` | 导入后~建纲前 | 块区间标记（requirement/noise/rule/review_table） |

**证据与矩阵写面**

| 工具 | 什么时候能调 | 干什么 |
|---|---|---|
| `register_evidence` | 矩阵就绪后 | 证据登记（四态验证：CONTENT_MATCHES/FILE_EXISTS/PLACEHOLDER…） |
| `bind_evidence` | 矩阵就绪后 | 证据批量绑定 + 矩阵重算（EXPIRED 禁绑） |
| `set_matrix_override` | 矩阵就绪后 | 人工覆写条款响应状态（否决项死锁出口；NOT_APPLICABLE 必带理由；receipt 验签） |

**审校与门**

| 工具 | 什么时候能调 | 干什么 |
|---|---|---|
| `record_review_gate` | 按门窗口 | 三门记审（matrix/outline/pre_export；receipt 验签，agent 声明留痕） |
| `record_addendum_waiver` | 导入后任意时刻 | 补遗逐件人工确认（分级阻塞的免责面） |
| `recover_validating_state` | 仅 VALIDATING 态 | 历史异常态恢复（缺章回 DRAFTING，审计账） |

**评分（只读试算）**

| 工具 | 什么时候能调 | 干什么 |
|---|---|---|
| `score_price` | 随时 | 价格分试算 + 最优报价反推（纯计算器） |
| `score_section` / `score_document` | 矩阵就绪后 | 章节自评 / 整本自评（四维规则 + 逐评分项映射） |

**分段写作（长章节安全续写）**

| 工具 | 什么时候能调 | 干什么 |
|---|---|---|
| `append_section_segment` | 矩阵就绪后 | 追加章节分段（真增量，前段不丢） |
| `rewrite_section_segment` | 矩阵就绪后 | 局部段重写（expected_version CAS） |
| `list_section_segments` | 随时 | 段账本对账（合稿字数 + 剩余配额） |

**补遗增量（起草后补遗到达）**

| 工具 | 什么时候能调 | 干什么 |
|---|---|---|
| `register_addendum_changes` | 矩阵就绪后 | 变更登记 → DIRTY 打标 + 改写指令生成 |
| `rewrite_section_partial` | 矩阵就绪后 | 局部改写 + 局部复验（只改指令影响面内的段） |

**修订任务与分工（审校闭环）**

| 工具 | 什么时候能调 | 干什么 |
|---|---|---|
| `assign_revision` / `advance_revision` / `complete_revision` | 矩阵就绪后 | RT 认领/推进/关单（BLOCKER finding 派生；**全部关单才放行导出**） |
| `batch_task` / `advance_task` | 矩阵就绪后 | 分工批量派工 / 单件推进（人的进度轴） |
| `reopen_section` | 起草后 | ACCEPTED 章节重开（→ REVISING + dirty，重过验收链） |
| `set_param_responses` | 抽取后 | 技术参数应答写入（偏离表唯一录入面，导出自动判定真偏离） |

**状态机**（越级调用会被拒——`E_STATE`）：

```
DRAFT → FILES_IMPORTED → REQUIREMENTS_EXTRACTED → MATRIX_READY
      → EVIDENCE_BOUND → DRAFTING → VALIDATING → REVIEWING
      → READY_TO_EXPORT → EXPORTED
```

**出错码**（按码分支，不解析消息文本）：

| 码 | 含义 | 该怎么办 |
|---|---|---|
| `E_STATE` | 状态机越级 | 先看 `get_bid_project_state`，按序推进 |
| `E_CONFLICT` | project_version 过期 | 重取状态后再调 |
| `E_NOTFOUND` | 对象不存在 | 检查 project_id / section_id |
| `E_UNPROCESSABLE` | 参数/前置不满足 | 看消息里的具体指引 |
| `E_PARTIAL` | 部分失败 | 逐件核对返回清单 |

---

## 五、LLM 配置（真实 AI 生成）

### 5.1 api_key 放哪（两处，env 优先）

**方式 A：项目工作区配置文件**（推荐——随项目走）：

```
{工作区}/.mang/llm.json
{
  "api_base": "https://api.openai.com/v1",   // 任何 OpenAI 兼容端点（DeepSeek/z.ai 等同款）
  "api_key":  "sk-……",
  "model":    "……",                           // api_key 在场时必填
  "timeout_secs": 60,                          // 可选，缺省 60
  "temperature": 0.3,                          // 可选，缺省 0.3（标书文风偏稳）
  "max_tokens_cap": 8192                       // 可选，缺省 8192（单章防失控）
}
```

**方式 B：环境变量**（CI / 本地免写盘）：

```
BID_LLM_API_BASE   覆盖 api_base
BID_LLM_API_KEY    覆盖 api_key
BID_LLM_MODEL      覆盖 model
```

⚠️ `.mang/llm.json` 已在 `.gitignore`（含密钥绝不入库）；密钥也绝不进日志与用量台账。

### 5.2 真实生成 vs mock 的区别

| | mock（缺省降级） | real（配了 key） |
|---|---|---|
| 内容 | 确定性模板句（同输入字节级同输出——e2e 可复现） | 真实 AI 写作（按章节素材逐条响应） |
| 怎么触发 | 未配 api_key 自动降级（告警「降级 mock」） | 配 key 自动启用；或显式 `generator: "real"` |
| 强制 mock | `generator: "mock"`（显式选择无告警） | — |
| 显式要 real 但没 key | — | `E_UNPROCESSABLE` 响亮拒绝（不静默降级） |
| 引用回查 | 生效 | 同样生效（幻觉引用剔除 + 告警） |
| 覆盖度检查 | 生效 | 同样生效（未回应条款 warning + `stats.uncovered_requirements`） |
| 版本快照/断点续跑 | 生效 | 同样生效 |

判断当前用的哪个：返回的 `stats.generator` 字段（`"real"` / `"mock"`）。

### 5.3 成本预估与控制

- **用量台账**：每次真实调用累计落 `{工作区}/.mang/llm-usage.json`（calls / prompt_tokens / completion_tokens / total_tokens / by_model）——随时查总账；
- **单章上限**：`max_tokens` 按目标字数自动推导（target × 3 + 400，上限 `max_tokens_cap`）——生成失控（服务端忽略上限超 2 倍）整章废弃报错；
- **超时重试**：60s 超时自动重试 1 次（共 2 次尝试）；失败走 `assemble_all` 的 3 次指数退避重试，仍失败标记 FAILED 不阻塞其他章；
- **粗估**：中文 1 字 ≈ 1-2 token。一章 2,000 字 ≈ 输入 2-4k + 输出 3-6k token；50 万字标书（252 章）≈ 全链 200-400 万 token 量级——**建议先单章试跑看台账再全量**。

---

## 六、格式规格（.mang/format-spec.json）

**格式从招标文件读，不硬编码**——每份标书要求不同。

```json
{
  "global": {
    "page": { "size": "A4", "margin": { "top": 35, "bottom": 30, "left": 28, "right": 26 } },
    "font": { "body": "仿宋_GB2312", "size": 12, "lineHeight": 1.5 },
    "header": { "enabled": true, "content": "{project_name}" },
    "footer": { "enabled": true, "content": "第 {page} 页 共 {pages} 页" }
  },
  "per_section": {
    "技术方案": { "font": { "body": "黑体", "size": 14, "lineHeight": 1.5 } }
  }
}
```

三级优先级：

1. **手写 spec**：工作区放 `.mang/format-spec.json` → 直接用（人工核过的最准）；
2. **条款提取**：招标文件里的格式条款（「正文用仿宋三号，行距 1.5 倍」）
   自动识别（中文字号表/字体族/行距/四边边距；补遗覆写主文件）；
3. **工程基线**：都没命中 → A4 / 仿宋_GB2312 小四 / 1.5 倍行距 / 35-30-28-26mm
   （水利标书主流口径）+ **响亮告警**（不静默降级——形式评审风险要人工确认）。

占位符：`{project_name}`（页眉）、`{page}` / `{pages}`（页脚页码域）。

---

## 七、暗标模式

导出时传 `profile`：

```json
{ "dark_bid": true, "bidder_name": "某某建设工程有限公司" }
```

效果：正文与章标题里的公司名 → 「投标人」（评审禁公司名的暗标规矩）。
**漏配 bidder_name 会响亮告警**（无名字可替不是错误，但不静默裸导）。

---

## 八、常见问题

**Q：跑 `cargo test` 有的测试显示 SKIP？**
环境缺依赖（soffice/pdftotext/真件）——SKIP 横幅会写明缺什么。缺件不是
业务失败；装上依赖重跑即测。

**Q：导出被拒「N 条必选未响应」？**
防废标门在工作。两条路：给必选条款绑证据（`bind_evidence`），或人工覆写
响应状态（`set_matrix_override`——不适用必须给理由）。

**Q：AI 生成的引用是编的？**
两层防线：draft 时引用回查（未知 REQ/EV 剔除 + 告警）；validate 时
`E_CITATION_GHOST` 规则（BLOCKER——评标查证无此件是废标级）。

**Q：想看每一步耗时？**
`cargo test -p bid-mcp --test scale_1330 -- --nocapture`——50 万字 252 章
全链逐步计时（实测全链 19s：起草 18s + 导出 0.3s）。

**Q：PDF 和 docx 哪个先出？**
docx 是真源（PDF 由 docx 转换）。PDF 需要 LibreOffice（`soffice`）——
缺失时 docx 通道不受影响。

**Q：PDF 导入被拒，报「CJK 乱码 + 原因定位（#200 能力边界）」？**
该 PDF 用了纯 Rust 兜底解不出的编码形态（报错里会点名具体是哪种）：
- `GBK-EUC-H / GB-EUC / B5pc` 等**非 UCS2 预定义 CMap**——码值是 GBK/Big5
  本地码值而非 Unicode，正确解码需内置映射大表（不硬解——硬解会产出
  乱码文本，比失败更危险）；
- **Adobe-GB1 等 CID 注册序号**（无 ToUnicode）——码值是 Adobe 注册表
  字形编号，与 Unicode 无恒等关系；
- **/ObjStm（PDF 1.5+ 对象流）**——字体字典被压缩，兜底扫描不到编码
  声明。

三条绕过（任选其一）：① 安装 pdfium（首选路自带 CMap）；② 安装带
poppler-data（CMap 资源包）的 poppler；③ 用 Word/WPS 打开该 PDF 另存为
DOCX 后导入（docx 是本系统真源格式，解析最完整）。

**Q：生成的是模板句不是真内容？**
没配 api_key——auto 模式降级 mock（告警里有「降级 mock」字样）。配好
`.mang/llm.json` 或环境变量后重起草即走真实生成（`stats.generator` 可验）。

**Q：真实生成的费用怎么查？**
`{工作区}/.mang/llm-usage.json`——按模型分列的累计 token 台账。

**Q：怎么知道哪些章需要人工处理？**
`check_bid_quality` 一键体检：`needs_human` 清单 = FAILED 章 + 有未回应
条款的章 + 幻觉引用 + 字数带外；报告落 `artifacts/quality-report.json`。

**Q：重启后进度还在吗？**
在。工作区三件套：`db.json`（状态机）+ `chapters/*.json`（章内容）+
`export-manifest.json`(导出幂等)——重启全量恢复，已完成章不重跑。

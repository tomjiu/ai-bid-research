# P4 证据细则（register_evidence / bind_evidence / list_evidence）

> 契约依据：仓库根 `docs/bid-mcp-contract.md`（路径约定见 SKILL.md 头部——`docs/` 指仓库根，非本目录相对） §11-A / §11-B / §4-A。外部 Agent 纯
> MCP 驱动的证据三板斧：**登记（register）→ 绑定（bind）→ 盘点（list）**。
> `search_evidence`（知识库双通道检索，契约 §5）已接线（#145 朴素实现 +
> #217 正文摘录面）——选证/续绑前可用它查找；真向量库与游标信封属
> M2-b（见文末）。

## 登记面（register_evidence）

```json
{
  "project_id": "…",
  "kind": "qualification",
  "title": "电子与智能化工程专业承包二级资质证书",
  "source_file_id": "TF-0003",
  "subject_name": "投标人",
  "scope": "电子与智能化工程",
  "valid_until": "2028-06-30",
  "locator": { "kind": "pdf_page_text", "page": 1,
               "text_fingerprint": "fnv64:…" },
  "project_version": 12
}
```

- `source_file_id`（#185 来源验证，必填）：**已导入文件**的 TF-id——从
  `import_tender_files` 回执 `per_file[].file_id` 拿。不存在 / 解析失败件
  → 拒；sha256 与指纹由服务端从库内与实际内容生成，**不接受自报**
  （旧参数 `source_file` / `source_sha256` / `fingerprint` 已废除，传入即拒）；
- `locator` 可选：缺省 = 文件级锚（指纹退 `sha256:<库内 sha>`）；传入则与
  该文件解析产物**对账**——`docx_paragraph`（paragraph_index 是正文段
  0 起序，表格行不占号）/ `pdf_page_text`（page 1 起在解析页数内），且
  `text_fingerprint` 须与实际内容一致（越界/不符 → E_UNPROCESSABLE）；
  其他形态（xlsx_cell / markdown_block 等）无对账面，显式拒；
- `kind` 七种：`qualification | performance | personnel | certificate |
  product_doc | solution_module | contract`（或对应中文展示名）；
- 语义位查重：同 `kind+title+subject+scope` 的最新非 SUPERSEDED 记录——
  同指纹**且同验证态** → 幂等重放回原 EV-id；异指纹或异验证态 → 旧记录
  单向降级 SUPERSEDED + 签发新 EV，**旧记录既有绑定自动迁移到新记录**
  （证书换版就这么处理；#245：占位→真实升级同路径）；
- 切块即入 EV 台账：`import_tender_files` 的切块已自动注册 EV——**后续
  register 签发的 EV-id 从已有计数后继，不是从 EV-0001 起**；
- 返回 `{ ev_id, deduplicated, status, verification_tier, placeholder, hint }`
  ——`deduplicated: true` 即重放。

### 占位/待核验登记（#245——占位资质不得冒充已核验证据）

```json
{ "project_id": "…", "kind": "qualification", "title": "iso9001 质量管理体系认证",
  "source_file_id": "TF-0002", "subject_name": "投标人", "scope": "…",
  "placeholder": true }
```

**真实证据 vs 占位材料的区别（必读）**：

| 维度 | 真实证据（CONTENT_MATCHES / FILE_EXISTS） | 占位材料（PLACEHOLDER） |
|---|---|---|
| 声明方式 | 带 locator 登记即得 / 缺省文件级锚 | `placeholder: true`（可自报——从低不从高） |
| 矩阵作用 | 绑定 → RESPONDED/PARTIAL，blocking 清零 | 绑定 → **PENDING_EVIDENCE 待补**，必选行 **blocking 保留** |
| 起草作用 | 生成器引用实料（依据 [EV-*]…具备可核验支撑） | 生成器落【待补：...】占位——**不引用编号、不声称已具备** |
| validate | — | E_EVIDENCE_PLACEHOLDER / E_QUAL_UNMET（BLOCKER） |
| 导出 | 过门 | **1d 占位证据门拒（即使三门全批）** |
| 升级 | — | 导入真实材料重新登记（同语义位换版：旧记录留痕 + 绑定迁移） |

Agent 纪律：
1. **不得自报已验证**：`verification_tier` 参数不存在（传入即拒）——
   验证态由服务端裁决；占位→真实没有原地迁移通道，只有换版重登；
2. 占位绑定回执会明示「不清除合规阻塞」——不要把 blocking 未归零当作
   绑定失败去重试，那是占位语义的诚实呈现；
3. 事故教训（2026-11-05）：批量注册占位资质并绑定全部矩阵行曾被误读为
   「阻塞已清零/真实资质已满足」——占位绑定只产生待补面，导出前必须
   升级为真实证据或合法人工豁免（NOT_APPLICABLE 覆写 + 非空偏离说明 +
   可信 Human receipt——**Responded 等普通状态覆写不豁免占位门**，
   #247 审核口径）。

## 绑定面（bind_evidence）

```json
{
  "project_id": "…",
  "ev_id": "EV-0007",
  "requirement_ids": ["REQ-0012", "REQ-0013"],
  "bid_open_date": "2026-11-30",
  "project_version": 14
}
```

- `bid_open_date` 语义（易错点）：证据有效性的**裁决基准日 = 开标日**
  （评标时刻的有效性），不是 create 时的 bid_deadline（递交截止日）——两者
  通常相近但语义不同；无独立开标日真源时用招标文件载明的开标日期；
- EXPIRED / SUPERSEDED 证据禁绑（开标日视角即时裁决 → 逐件
  E_UNPROCESSABLE）——**不要试图绑过期待换证的证据**，先走补料流程；
- 绑后矩阵即时重算：返回 `matrix.blocking`——真实证据绑齐时清零；
  **占位证据（#245）绑定不清零**（必选行 PENDING_EVIDENCE 仍 blocking，
  回执 `placeholder: true` + hint 警示）；
- 重复绑定幂等重放；部分失败 → E_PARTIAL（item_errors 逐件定位 + data 携
  带成功面）。

## 盘点面（list_evidence，只读）

```json
{ "project_id": "…", "filters": { "kind": "performance", "status": "ACTIVE" },
  "cursor": "<opaque>", "limit": 100 }
```

状态四态：`ACTIVE | EXPIRING | EXPIRED | SUPERSEDED`。大结果统一游标信封
（`next_cursor: null` 即取完；行序 = id 字典序）。游标与过滤器绑定——换过滤
器必须换游标，跨工具复用 → E_UNPROCESSABLE。`limit` 合法域 1..=1000、缺省
100，越界显式拒不静默 clamp。

## 有效期核对法（Agent 逐条核对模板）

对每条资格/业绩证据：

1. 读 `valid_until`，与 `bid_open_date` 比较；
2. `valid_until < 开标日` → EXPIRED：**禁绑**，进补料清单；
3. 临界（开标日前 90 天内到期）→ EXPIRING：可绑，但向用户提示换证风险；
4. 无 `valid_until`（如业绩合同）→ 不参与有效期裁决，正常绑。

## 补料清单模板（缺失项交用户）

> **证据缺口清单（P4 产出）**
>
> | REQ | 条款摘要 | 需要的证据 | 现状 |
> |---|---|---|---|
> | REQ-0015 | 电子与智能化二级资质 | 资质证书扫描件（sha256） | 待用户上传 |
> | REQ-0031 | 近三年类似业绩≥2 项 | 中标通知书+合同关键页 | 缺 1 项 |
>
> 请补齐后告诉我文件路径，我会登记并只补跑受影响的绑定行。

用户补料 → register（新 EV）→ bind（只绑受影响 REQ）→ 矩阵复blocking=0。
不要整单重跑（恢复协议：缺料只补受影响行）。

## 业绩材料库（#315——跨项目业绩资产，四工具）

> 业绩是投标人的**长期资产**（评标常占 10-20 分），不是单项目的输入。
> 库文件在项目工作区**之外**：`BID_PERF_LIB` 环境变量 → 用户级默认位
> （Unix `$HOME/.mang/performance-library.json` / Windows
> `%APPDATA%\mang\performance-library.json`）→ 内存态（本会话可用、
> 不落盘，响应面 `library_persisted:false` 如实报告）。原子写 +
> `schema_version` 门 + 损坏拒载不重建。契约详见 bid-mcp-contract.md
> §25-A~D。

### 何时用（主流程挂点）

| 时机 | 动作 | 工具 |
|---|---|---|
| **任何时刻**（建项目前也可——四工具无项目路由/低门） | 把历史合同/验收报告登记入库（语义四元组 `name+client+amount_wan+completed_on` 幂等去重；`owner_name` 一次登记全程生效——证据 `subject_name` 默认源） | `register_performance` |
| P4 盘点时 | 按标签/关键词/金额/日期查库，看可复用面 | `list_performance` |
| REQ 抽取后 | 四因子匹配推荐（见下），**推荐排序、人工裁决**——分数是排序依据不是正确率 | `recommend_performance` |
| P5 起草业绩章节时（窗口 MATRIX_READY+） | 一键写入业绩表 + 逐条描述段到目标叶章节 | `write_performance_section` |

### 与本页证据纪律的衔接（关键——不是旁路）

- `write_performance_section` **走的就是本页 EV- 纪律**：材料文件名与已导入
  TF 命中 → 自动 `register_evidence`（kind=performance；主体名链：
  条目级 `subject_name` > 库主 `owner_name` > 工作区 bidder-profile.json
  的 `company_name`）→ 自动 `bind_evidence` 到业绩类 REQ（陈述含
  业绩/类似项目）→ 矩阵重算。产出的业绩章每条带 `[EV-*]` 引用——
  **无引用即 P6 拦截（E_CITATION_GHOST）**，库路径不豁免。
- **诚实面**：材料未导入/无主体名 → `materials_pending` 逐条列明（正文照
  写、证据不伪造——导入材料后重跑自动补登记，域层查重天然幂等）；
  可用业绩证据 < 3（MIN_PERFORMANCE_COUNT）→ readiness 门拦写入并把
  材料指引带全。
- **有效期口径一致**：业绩合同无 `valid_until` → 不参与有效期裁决（同
  本页「有效期核对法」第 4 条），但**近三年**仍是 `recommend_performance`
  的独立打分因子（完成日距评标基准日 <=3 年满分）——两码事不要混。

### 推荐语义（读结果时对用户怎么说）

四因子确定性加权：标签重叠 40% / 金额规模 30% / 近三年 20% / 客户类型 10%；
**缺信号因子弃权重归一**（`available:false` 不参与分母——「不知道预算」
不惩罚业绩）。同分按 perf_id 字典序（确定性——同输入恒同序）。向用户
呈现时逐条给 `reasons`（逐因子人读依据），并保留裁决权：选哪几条由
用户定（`top_k` 只控返回条数）。

### 幂等与重跑

`register_performance` 四元组命中既有条目回显 id 不重复登记；
`write_performance_section` 幂等键 `perf-section:<section_id>`（同批
重跑 no-op）。**补材料后重跑**是正常操作路径（materials_pending 清零），
不会产生重复段或重复证据。

## search_evidence 双通道（已接线——#145 朴素实现）

- 模式三选：`hybrid`（缺省，语义+精确合并去重——双中 `match_type=both`，
  分取 exact 的 1.0）/ `semantic` / `exact`；
- **资格类查询默认 exact 优先**（证书号/金额/日期/型号——精确命中即够，
  语义召回反而引入噪声；exact 五字段：model / amount / date / clause_no /
  cert）；
- `filters`：`source_type` / `valid_at`（开标日）/ `min_valid_until`；
  `top_k` 1..=1000（缺省 20，越界显式拒）；`threshold` 0..=1.0（作用于
  降权后的分值）；
- `valid_at` 在场时：`valid_until < 开标日` 的证据自动降权（score×0.5）并
  附 warning（EVIDENCE_EXPIRED）；不足 90 天 → EVIDENCE_EXPIRING（可绑但
  提示换证）；
- 排序确定性（score DESC, ev_id ASC）——同查询同结果，可重放；
- hits 携带 #217 三面（`excerpt` / `excerpt_locator` / `verification_tier`）
  + 台账直通附加面（kind / title / status / valid_until）——检索命中可直接
  看实料，非标题转写；`trace` 回显双通道命中数与 content_face；
- **M2-b 待办**：真向量库（当前是 token/子串朴素引擎——`trace.engine`
  自标记 naive-token-v1）与统一游标信封（当前 top_k 截断，非分页）。

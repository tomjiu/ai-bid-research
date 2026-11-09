# 风险登记册（Risk Register）

> 严重度：BLOCKER（不解决不能上线）/ HIGH / MEDIUM / LOW。
> **v2 变更（评审反馈落实）**：① 修正 3 处测试映射错误（R-11→TC-12、R-14→TC-11、R-05↔TC-08 双向对齐）；② 新增三层保证模型（§1）——"确定性代码兜底"结论收紧为"确定性校验不等于确定性正确"；③ 新增全量追溯矩阵（§3）与残余风险列。
> 交叉引用词典：R-* = 本册风险；TC-* = test-plan 用例；AD-* = architecture-decision；Q* = workflow-audit 十项审计问题；M* = mvp-implementation-plan 里程碑。Q→R 映射见 §3 追溯矩阵。

## 0. 三层安全保证模型（对"确定性代码兜底"结论的收紧）

原结论"BLOCKER 级风险全部对应确定性代码手段"方向正确，但**确定性校验不等于确定性正确**。每个缓解措施按以下三层归类，明示程序能保证什么、不能保证什么：

| 层 | 应当保证什么 | 程序可否完全保证 | 残余风险的归宿 |
|---|---|---|---|
| **L1 输入完整性** | 源文件、页、表格、附件的处理情况可核对：每文件有 parse_status、失败页清单、块数统计；失败位置明确；失败件禁引 | **部分可保证**（处理面可穷举核对），"未编号条款/附件条款/跨页表格的遗漏"不可由编号序列校验发现 | 导入报告必须经 Agent **复述核对 + 人工抽查**（Skill 阶段门禁 P2）；真实结构分布测试集回归 |
| **L2 规则正确性** | 日期、金额、型号、资格、格式等**可机械验证的规则**执行正确：有效期断言、报价上限、禁字扫描、页数、引用覆盖计数 | **可保证规则执行正确**，但前提是 L1 输入正确（OCR 字段源头错误会流入规则）且**规则本身对招标文件语义的解释正确**（如"有效期以开标日还是投标截止日为基准"） | 规则解释歧义登记为 finding 交人工裁决；规则集按采购场景显式版本化（AD-07） |
| **L3 语义正确性** | 条款解释、证据与承诺之间的**支持关系**真实成立 | **不可仅靠程序保证**。"有引用 ID"不等于"引用内容支持该句"；"检查通过"不等于"理解正确" | 评审意见原文采纳：Synthesized/推断型主张**默认必经人工确认**（与引擎 ReviewStatus 三态对齐，见 doc-engine-audit §3）；模型检查仅产 finding 不改稿 |

**推论**：下表缓解措施标注所属层（L1/L2/L3/工程）。**任何"100% 拦截"的宣称只对 L2 的规则执行成立**；L1 残余靠核对纪律，L3 残余靠人工审校门禁——这二者是流程要求，不是代码断言。

## 风险登记表

| ID | 风险 | 证据来源 | 严重度 | 缓解措施（保证层） | 验证方法 |
|---|---|---|---|---|---|
| R-01 | 长招标文件（附件/表格/扫描件）条款因截断、解析失败、分块遗漏而丢失 | 审计 Q1：18 仓库无一完整解决；LingYan 仅做到降级禁引 | **BLOCKER** | 确定性解析器（表格单元格级+扫描 OCR 分档）+ 条款编号序列完整性校验 + 解析失败件隔离禁引 + 导入返回块数/失败清单供 Agent 核对（L1+L2；**未编号条款遗漏属 L1 残余**，靠核对纪律与真实分布测试集） | TC-01 埋点完整性（目标 100% 召回） |
| R-02 | 语义检索无法精确命中编号/型号/金额/日期，证据错配 | ark 双路检索、rag-tender FTS5 实证该风险真实存在 | **BLOCKER** | search_evidence 双通道：语义召回 + 结构化精确索引；金额日期归一化（L2；检索结果与查询的**语义相关性**属 L3 残余） | TC-02 精确匹配（目标 100%） |
| R-03 | 资质过期/证据过期仍进入定稿 | ark 资格三态闸门是该领域唯一显式实现 | **BLOCKER** | 资质有效期 vs 开标日确定性断言（L2 日期计算）；EXPIRED 证据禁止绑定。**L2 残余**：日期对但"选错资质文件/有效期基准解释错"→ 规则解释 finding 交人工 | TC-03 矩阵覆盖；TC-05 确定性规则命中；TC-09 开标时间变更触发有效期重检 |
| R-04 | 无证据支撑的"满足/无偏离"表述（模型幻觉承诺） | ark SKILL 明文要求"任何'满足'必须引用至少一条有效证据" | **BLOCKER** | 章节起草强制绑定 evidence_ids + 承诺句引用覆盖率计数（L2 可机械查"有没有引用"）；**L3 残余**：引用存在≠引用支持——独立评估 + 人工确认（引擎 ReviewStatus：AI 提出的关联一律 Pending） | TC-03 矩阵覆盖；TC-04 引用存在率（目标 100%）；引用支持率进 L3 人工抽检（test-plan §5） |
| R-05 | 中断/换模型/补文件后整单重跑或新旧产物混用 | LingYan freshness 机制存在的原因；BidMaster/claude-bid-gen 均有恢复方案 | HIGH | 后端状态机 + 断点恢复 + 影响面分析（content_version 依赖追踪，DIRTY 重跑）（L1/L2 确定性代码） | TC-06 断点恢复；TC-08 换模型恢复；TC-09 补遗影响面 |
| R-06 | 幂等缺失导致重复导入/重复生成 | 通用工程风险 | HIGH | 文件 sha256 幂等；工具幂等键；ACCEPTED 前置校验（L2） | TC-07 |
| R-07 | 模型审校假阳/假阴（漏放错误或误报阻断） | claude-bid-gen 用确定性脚本替代模型审校的动机 | HIGH | 规则分层：确定性规则白名单（L2）+ **模型检查仅产 finding 不改稿（L3 定位**）；抽检回放集回归 | TC-05 回放 |
| R-08 | Dify KB API 外部依赖风险（分块黑盒/版本漂移/全家桶运维/云版出域） | 官方文档核验：DSL/KB API 版本多次变更；llm_bidwriting 绑死 0.5.0 | HIGH | KBAdapter 隔离：自建默认，Dify 仅 A/B 对比适配器 + 锁版本契约测试（工程） | TC-10 检索质量 A/B |
| R-09 | 数据出域（标书/资质为高敏数据） | Cherry/Dify Cloud 均为 SaaS 路径 | **BLOCKER** | 私有化部署红线；企业资料库仅本地/内网；禁止云 KB 上传企业证据（L2 部署面断言 + 出口清单审查） | 部署检查单（test-plan §3 记录口径）；TC-10 限定自托管实例 |
| R-10 | 开源许可证合规（AGPL 传染/无 LICENSE 复用） | BidMaster README 徽章 MIT vs LICENSE 文件 AGPL 冲突；3 仓库无 LICENSE | HIGH | 复用白名单仅 MIT/Apache（7 家）；引用任何代码前以 LICENSE 文件为准（工程） | repository-matrix 合规节 |
| R-11 | 暗标格式违规（公司名/字体页边距越界/页数超限）导致废标 | claude-bid-gen "显式硬约束搜索"实战教训；rejection-check 三轮检查的存在 | **BLOCKER** | 暗标模式确定性检查：禁字清单扫描 + 页数（Word 渲染口径）+ 格式断言；导出前置校验强制通过（L2 规则执行 + L1 导出件与编辑态一致性）。**L3 残余**：版式合规（字体度量级）需渲染级复验 | TC-05 禁字规则命中；TC-12 暗标导出（v2 修正记录见文首变更说明） |
| R-12 | 业务状态锁进平台（Dify/框架）取不干净，迁移成本失控 | llm_bidwriting 实证：业务状态一半在 Dify 平台库 | HIGH | AD-01：状态机自持于后端数据库；外部平台只做无状态能力调用（架构） | 架构评审；对照实验 EXP-1 迁移面记录（verification-plan §4） |
| R-13 | 提示注入（招标文件正文内嵌"忽略规则"类指令） | LingYan 把防注入写进 Skill 纪律 | MEDIUM | 解析产物标记为**不可信数据**；Skill 纪律 + 敏感指令模式扫描（L2 扫描可穷举已知模式；**L3 残余**：注入不可穷举——纵深靠数据/指令隔离 + 工具参数化，非仅关键词扫描） | TC-05 规则 8；安全威胁模型补充（verification-plan §5.4） |
| R-14 | 低能力模型 Agent 自由规划跑偏（跳过矩阵/直接写稿） | tender-master"顺序锁死，禁止跨步"的设计动机 | HIGH | 封闭 Agent + Skill 阶段门禁 + 后端状态机 E_STATE 拒绝越级调用（L2） | TC-11 状态机越级防护（v2 修正记录见文首变更说明） |
| R-15 | 双路检索交替合并排序不稳，同一查询不同时间结果漂移 | ark alternatingMerge 无全局稳定排序（抽检发现） | MEDIUM | 检索结果确定性 tie-breaker（score, evidence_id）；查询指纹缓存（L2） | TC-02 重复执行一致性 |
| R-16 | 文件级验证输入（招标文件本体+补遗文件成对）获取受阻：附件在官方页面公开存在，但本环境全部二进制通道（curl/无头浏览器/公共代理/存档服务）被 ccgp WAF 阻断 | M1.7 执行实证（2026-10-26：四通道均 403；WebFetch 仅文本层） | HIGH | 公告级条款级配对先行闭环（更正公告逐条引用原招标文件条款原文）；文件本体转人工获取（GT-M17-24）；获取后入 T14 复验 | T14b（公告级已验）；文件级待人工 |
| R-17 | 真实数据 GT 为初标草案未人工冻结，相关准确率被误当正式验收结果 | 用户裁决口径（2026-10-26）：未冻结前仅作探索性指标 | MEDIUM | review_status=draft_pending_human 全量机检（T14 P4）+ EXPLORATORY 标注纪律 + 冻结协议（接受/退回修订，不凑数） | T14 P4（24 条字段完备+逐字读回+引擎吻合） |

## 处置优先级建议

1. **第一梯队（阻断上线）**：R-01、R-02、R-03、R-04、R-09、R-11 —— L1/L2 层以确定性代码为主，L3 残余以人工门禁收口；**"确定性"宣称严格按 §0 三层边界表述**。
2. **第二梯队（稳定性）**：R-05、R-06、R-14 —— 状态机 + 幂等 + Skill 门禁三件套。
3. **第三梯队（工程卫生）**：R-07、R-08、R-10、R-12、R-13、R-15 —— 以契约测试与合规清单固化。

## 追溯矩阵（风险 → 对应设计 → 实现模块 → 测试用例 → 残余风险）

> 评审要求落地：每一风险建立全链映射。"测试结果"列在 verification-plan 执行后回填；本矩阵即跨文档一致性检查的单一真源——**新增风险或用例时必须同步本表**（一致性检查脚本以本表为基准，见 verification-plan §2.4）。

| 风险 | 对应设计（AD/契约） | 实现模块（M*） | 测试用例（TC*） | 测试结果 | 残余风险（层） |
|---|---|---|---|---|---|
| R-01 | AD-03 确定性切块；MCP §2 import 返回统计 | M1 解析与条款（bid-parse/bid-tools） | TC-01 | TESTED | 未编号/附件条款遗漏（L1→核对纪律，corpus-R 真实分布测试集验证）；扫描件 OCR 路径为登记边界非伪装支持（B2/D5a） |
| R-02 | AD-03 双通道；MCP §5 search_evidence | M1 精确通道（bidcore/bid-kb + m1 并行线）；M2 补语义通道 | TC-02 | PARTIAL | 语义相关性误判（L3→人工抽检）；精确通道 TESTED（bidcore e2e 25 查询×5 一致 + m1 并行线 25/25 含数值归一化 3500000≡350 万元），语义通道 M2 落地后补测 |
| R-03 | MCP §5 valid_until 降权；MCP §7 确定性规则 | M2 + M4 | TC-03、TC-05、TC-09 | PARTIAL | 有效期基准解释错/选错文件（L2 规则解释 finding）；V2 R2 已验级联语义（SEMUL：基准日变更→全项目重检+精确翻转+零误翻） |
| R-04 | MCP §6 强制绑定；Skill P6 引用键纪律 | M3 + M5 | TC-03、TC-04 | PARTIAL | 引用存在但内容不支持（L3→ReviewStatus 人工确认） |
| R-05 | domain-model §2 DIRTY/content_version；MCP 通用 project_version | M1 状态机起 | TC-06、TC-08、TC-09 | PARTIAL | 影响面规则漏判（设计假设→EXP-2 实测；V2 已验设计语义 SEMUL：DIRTY 恰三章节/无关零误伤/终裁门禁/幂等——run_tests T8） |
| R-06 | MCP §0 幂等策略 | M1（bidcore/bid-domain DomainStore） | TC-07 | TESTED | — |
| R-07 | AD-06 规则分层；MCP §7 DETERMINISTIC/MODEL | M4 | TC-05 回放 | 待执行 | 模型 finding 假阳干扰（回放集回归） |
| R-08 | AD-03 KBAdapter；MCP 附录 A | M6（可选） | TC-10 | 待执行 | 对比期检索质量不确定（A/B 结论归档） |
| R-09 | AD-03 数据边界；部署红线 | 全程约束 | 部署检查单、TC-10（限自托管实例） | 待执行 | 供应链面（镜像/模型出口）→ threat-model.md（S1 v1.0：15 威胁四组+审批矩阵；T-15 供应链待 M0 闭包审查） |
| R-10 | AD-06 白名单；repository-matrix §3 | M0 | 合规审查 | 待执行 | 传递依赖引入（NOTICES 式闭包审查） |
| R-11 | AD-05 页数口径；MCP §8 precheck 闸门 | M4 + M5 | TC-05、TC-12 | PARTIAL | 版式合规（渲染级复验，doc-engine-audit G6；G3 引擎侧缺口仍开，业务侧缓解已验） |
| R-12 | AD-01 状态自持 | 架构约束 | EXP-1 迁移面 | 待执行 | — |
| R-13 | domain-model 数据标记；Skill 纪律 | M1 + M5 | TC-05 规则 8 | 待执行 | 不可穷举注入（L3 残余→人工审校门禁收口；确定性解析层结构性免疫=T-10 TESTED 面，起草层见 threat-model.md） |
| R-14 | AD-02 路径 A；MCP E_STATE | M1 状态机（bid-domain） | TC-11 | TESTED | — |
| R-15 | MCP §5 tie-breaker | M1（bid-kb 四级排序） | TC-02 | TESTED | — |
| R-16 | 公告级条款级配对先行 + 文件本体人工获取协议（s2-scenario-plan §2） | M1.7 真实链（real-corpus/gov-procurement） | T14b | PARTIAL | 公告级闭环 34 断言全绿（REAL_DATA+DESIGN_ENGINE 口径）；文件级待人工输入，**不得宣称文件级验收** |
| R-17 | GT 冻结协议（s2-scenario-plan §2 M1.7-C） | gt/ground-truth-draft.jsonl 24 条 | T14 P4 | PENDING | 24/24 draft_pending_human；机器预核通过（engine 吻合/逐字读回/manual 计数=1）；冻结前指标仅 EXPLORATORY |

**验证状态注记（v0.5 合并口径——bidcore M1 端到端 + V1 四段验证双线回填；词典见 verification-plan §6）**：

- **R-01 → TESTED（双证）**：① M1 Rust 端到端（bidcore/bid-parse 四通道真跑 corpus-A，TC-01 召回 100%——160 REQ 全量抽取覆盖 25 GT，cargo test 12 用例全绿）；② V1-a 解析面基座（parse-report v1.0：文本层锚点 26/26 + corpus-R D1/D2/D5 探针 11/11 + 非正文盘点 5/5；run_tests T7a）。
- **R-06/R-14/R-15 → TESTED**：bidcore/bid-domain DomainStore 幂等 no-op（TC-07）、E_STATE 越级防护（TC-11）、bid-kb 四级确定性排序 tie-breaker（TC-02 精确通道）——cargo test 全绿。
- **R-03 PARTIAL**：V2 R2 已验有效期级联语义（SEMUL：开标日 11-15→11-27 → 全项目重检；GT-02 EV-02 恰翻转 EXPIRED；EV-13 维持禁绑细项 0 分；其余零误翻；run_tests T8）——TC-03/05 矩阵规则真跑待 M2/M4。
- **R-04 PARTIAL**：V1-b 定位器两级失效语义已验（SEMUL：10 链回查全 valid + 内容改写恰 1 链 stale_content + 结构漂移全体失效/书签重验恢复；run_tests T7b）；V3 Q1 五轮重写引用保持 + Q2 只降不升/不静默 adopt 再证（run_tests T9）——TC-04 引用支持率待 M3。
- **R-05 PARTIAL**：V1-b GT-18 补遗版本链入引用链（latest_version_wins 落地）；V2 影响面规则已验设计语义（SEMUL：TC-09 六断言契约消费 + DIRTY 恰三章节 + 开标日级联全项目重检 + 无关零误伤 + 矛盾终裁门禁 + 幂等 no-op；run_tests T8）——TC-06/08（中断/换模型恢复）待 M2，与 bid-domain Rust 双实现交叉验证待 cargo；V3 Q3 导出中断两阶段一致性已验设计语义（EXPORTED ⟺ sha256 落库；run_tests T9）。
- **R-11 PARTIAL**：V1-c/d 渲染级已验（LO headless：8 页硬断言 + 分页纪律 + 页眉页脚域；暗标四断言：禁字双面零命中 + docProps 清零 + 金丝雀防空洞绿；run_tests T7c/T7d）——Word/WPS 口径人工复验待（test-plan §5.5）。

**m1 并行线证据注记（合并自远端 51dfb79/ecd7d97——被测系统 = `m1/` Rust 单 crate 首轮实现，判分口径 verification-plan §3.1）**：
- R-01/TC-01：corpus-A 锚点覆盖 27/27=100%、对齐器召回 100%、parse_failures=0、missing_sequence=0；R-02/TC-02：exact 通道 25/25（含数值归一化）；R-06/TC-07：sha256 重放 no-op，files/chunks delta=0，双跑字节一致；R-14/TC-11：越级 draft_response_section → E_STATE 零副作用；R-15/TC-02：同查询 5 次结果完全一致（覆盖率→密度→导入序→块序确定性排序）。
- m1/ 为并行会话首轮实现（单 crate 最小流水线），bidcore/ 五 crate 工作区为同源演进版——本矩阵 TESTED 状态以 bidcore 证据为准，m1 证据作并行佐证随仓保留（m1 回归门禁见 run_tests T10~T13）。

**威胁模型 GAP 注记（S1 v1.0 建模发现，docs/threat-model.md；M1.5 已关闭——2026-10-25 a485a7b 实装 + R3 修复轮 f59b3f1/本轮 S3-1/S3-3/P2-4 加固）**：

- **T-03 压缩包炸弹限额（P1）→ IMPLEMENTED**：guard.rs 输入字节门 + prescan 三门 + 压缩比门 + 实际读取累计计量 + EOCD/zip64-EOCD 守恒门（S3-1 后 zip64 绕过封死）+ xlsx 读后行/单元格双轴门（S3-3）——负向 12 项 + xlsx 2 项全绿。
- **T-04 子进程超时（P1）→ IMPLEMENTED**：run_limited 超时杀进程组 + 溢出即时杀 + 五分类 + 并发门 + TmpGuard + OCR 页数门 + stderr 持续 drain（P2-4）——9 项测试全绿。
- 上述两 GAP 属 R-01 缓解面（解析失败件隔离）的加固项：**真实用户文件接入前置已兑现**（P2 第一轮真实文件评测 6a392d5 即在此防护下执行）。

**审计问题（Q1~Q10，workflow-audit）→ 风险映射**：Q1→R-01；Q2→R-01/R-02；Q3→R-04/R-07；Q4→R-02/R-15；Q5→R-03/R-04（矩阵闸门）；Q6→R-05；Q7→R-07（规则分界）；Q8→R-05（恢复）；Q9→AD-01/AD-02 实证基础；Q10→R-10。此前 test-plan TC-03/TC-08 直接引用 Q 编号，v2 起统一改为 R 编号（Q 映射保留在本行）。

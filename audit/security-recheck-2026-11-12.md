# 质量与安全审计（#122 · 审计阶段6）

> 基线：main（#121 合入后）。方法：旧安全审计（6105beb，十面总裁定）逐项核验修复现状 + 本审计新增实测证据（围栏实弹、receipt v2、原子写单源）。
> 结论分级：【已证实】【部分证实】【待验证】。

---

## 1. 八检查面复核总表

| # | 面 | 旧裁定(6105beb) | 现状 | 证据 |
|---|---|---|---|---|
| 1 | 路径/临时文件/穿越/symlink | PARTIAL | **强**（实测） | ① import 围栏**本审计实弹验证**：越界路径 E_UNPROCESSABLE 响亮拒（阶段3 真跑记录）；② save_version #374 围栏与 #183 同真源 + 防存在性 oracle + 防围栏外祖先 .mang 牵引（tools.rs:2265 注释自证）；③ write_fsync_atomic 单一真源（#546）tmp 残骸清理+目录项刷盘；④ TOCTOU v1 残余维持登记（自认债） |
| 2 | 上传安全 | PARTIAL+NEEDS_ENV | **部分**（维持） | 限额族（64 件/500MB/2GB）+ 字节门前置 + 引擎失败不推进状态（#174）；伪装扩展名面=引擎按内容拒（B-12 部分面维持登记） |
| 3 | 敏感泄漏 | PARTIAL→ | **强** | ① llm.rs 凭据纪律「绝不写日志」（头注自证）；② 暗标 docProps core/app BLOCKER+自动清零（FG-13 已修，darkbid.rs:18-19）；③ 掩码链路在位。**残余 SEC-N1（P3）**：llm.json 由用户手写、应用不强制 0600（部署注意事项，见 §3） |
| 4 | Prompt Injection | PARTIAL | **强（确定性层）** | ① 解析/抽取全确定性——注入文本只是数据（TC-05 八类命中）；② RealGenerator 输出仅成章节正文，经引用回查白名单+占位拦截——LLM 被诱导也只能产垃圾文，**无法触达工具调用**（结构性）；③ receipt v2 七段含 sections_digest（principal.rs:16-26，#323/R-06）——A-03「24h 窗对未审内容过门」已收口 |
| 5 | 工具权限 | —（新检查面） | **强** | 50 工具全走 route_guard（项目路由 E_NOTFOUND + guard_tool 状态机 E_STATE + check_version 乐观并发）；破坏性面（覆写/矩阵/导出/恢复）各有独立门；变异 M6 旁路杀伤 ✓ |
| 6 | Agent 边界 | PARTIAL | **强（一处结构性残余）** | Human-only receipt：HMAC-SHA256 + scope 进 MAC + 24h + 常量时间比对 + v2 内容摘要；三工具 reviewer/principal/operator 参数在场即拒；M5 变异击杀。**残余 C-10（P2，结构性）**：信任根=approval.key 同 uid 可读——威胁模型前置条件「宿主与 Agent 进程隔离」未成文（见 §3） |
| 7 | 损坏文件 | PARTIAL | **强** | ① bad_input_matrix.rs 负例族；② 解析失败件显式 Failed 不推进（#174）；③ OCR 页探测失败不留部分结果（tesseract.rs:129「不留部分结果：请修复 pdfinfo 部署或拆分文件」）——B-09/B-10 收口；④ 截断/乱码 fail-loud 仲裁（engines/mod.rs 六级判决，阶段2已核） |
| 8 | 导出完整性 | PARTIAL→ | **强** | manifest v2 inputs_digest 全指纹（换名/换证据触发全量重建不吃旧缓存）+ tmp+rename 原子 + GhostSection 门 + 组装失败 fail-closed（绝不静默跳章 export.rs:7）+ 门 1a-1m 十三门 |

## 2. 旧审计十面修复收口对账

| 旧发现 | 修复 | 现状 |
|---|---|---|
| P0-2 证据伪造链（T-12 ABSENT） | #245 tier/占位三要件 + 门 1d + SKILL 双条件 | 已修（阶段2链路核+FG-17 收口） |
| A-03 receipt 不绑内容 | #323 v2 七段 sections_digest | 已修 |
| FG-13 暗标 docProps 产品面缺失 | darkbid.rs 九类泄露面 | 已修 |
| C-06 save_version 无围栏 | #374 围栏同真源 | 已修 |
| B-09/B-10 OCR 截断不可见 | 不留部分结果 | 已修 |
| C-08/C-09 SDK 不传版本号 | SDK 断言 project_version 递增/重放不变 | 已修（消费面在位） |
| A-21 llm.json 0600 | —（部署面） | 残余 SEC-N1（P3） |
| C-10 信任根文件可读性 | —（结构性） | 残余（P2，需文档化前置条件） |
| B-12 引擎路乱码仲裁 | engines/mod.rs 仲裁器（#200） | 已修 |
| EOCD 四门（T-03） | 引擎侧（mdcore） | mdcore 责任面（rev 钉 f4328eb 对账工作流在位）——跨仓不重复报 |

## 3. 新登记（转阶段7）

| 编号 | 级 | 项 | 建议 |
|---|---|---|---|
| AUD2-SEC-1 | P3 | llm.json/approval.key 部署权限无成文要求（write_fsync_atomic 按进程 umask 落盘） | docs/agent-integration.md 补「敏感文件 0600 + 宿主隔离」部署节（与 C-10 同段成文） |
| AUD2-SEC-2 | P2 | C-10 结构性信任根未文档化——「宿主与 Agent 进程隔离」是 receipt 防线的隐含前置条件 | 威胁模型成文化（不改代码——单机单用户部署下攻击面=本机进程，属部署边界非代码缺陷） |

## 4. 阶段6结论

安全面自 6105beb 旧审计后实质性增强：P0 级证据伪造链、receipt 内容绑定、暗标产品面、save_version 围栏、OCR 截断可见性全部收口，且本审计以实弹（越界导入拒绝）+ 源码双证复核。剩余两处均为**部署边界成文化**问题（SEC-1/SEC-2），无新增代码级 P0/P1 安全缺陷。工具权限与导出完整性两面为本审计新增检查面，结论正面（五十工具全门禁+十三导出门 fail-closed）。

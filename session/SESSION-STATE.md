# 会话状态——Agent-hd2k4（迭代二段，更新于 R38 完成）

## 身份与纪律
- Agent-hd2k4 ｜ git user 已配（core.fileMode=false 与 codeberg remote
  需每次沙箱重置后重设——sync_codeberg.sh 已内置 remote 自愈）
- GitHub 账号 suspended（全 API 403）；一切推送走 Codeberg：
  mingjiu/ai-bid-research，token 在历史记录中
- 铁律：每轮 commit（Co-Authored-By: Agent-hd2k4）→ push codeberg；
  测试不过不提交；Codeberg 不通走 scripts/upload_fallback.sh（temp.sh
  3 天免登录，已验证上传+下载双通）
- CI 零触发：仓库 has_actions=false（勿开）；PR 标题带 [skip ci]

## 当前战役：#601 迭代二段（R31-R60，预存计划见 pr-drafts/601-iterate-plan.md）
- 分支 feat/601-iterate（基于 feat/601-extract @ 224a29c）
- **已完成 R31-R38（8/30）**，测试 305 → 389 绿 + 2 skip，8 提交全在 codeberg
- R31 CSV 读取器 7c029ce / R32 注册表 c02c4c2 / R33 健全性 a5eda48 /
  R34 db export 3801a4f / R35 采购人画像 9272366 / R36 交叉表 5081da7 /
  R37 术语演化 169710d / R38 集中度趋势 c5a756d
- 下一轮：R39 报告 SVG 图（标准库生成柱/折线 SVG 嵌 HTML 报告）

## 关键事实
- Codeberg 分支全景：main=347e0c1 真实历史；feat/601-extract=29 提交
  （PR #2 成果存档）；feat/601-iterate=迭代二段；backup/* 46 支在飞备份；
  backup/session-notes=会话产物；snapshot/baseline-753a3e9=旧快照保全
- PR #1（另一并行 601 线，feat/601-collect@e83bca5）与 PR #2 互斥取舍听 Lead
- Codeberg 有并行操作者（main 曾被外部移动、PR #1 标题被改）——推送注意冲突
- 沙箱重置后：pip install -r requirements.txt（pytest 依赖）；repo 幸存
- **教训：同一消息内 Edit 与 Bash 并行竞态——改文件与跑测试必须分消息串行**
- pytest 全量 <3s；提交信息里的测试计数务必用实际数字（勿凭印象）

## 仓库结构速查（Python 面）
- src/collect/（sources/records/dedupe/normalize/sanity R33）
- src/extract/（extractor/validator/store/pending）
- src/analyze/（dataset/stats/keywords/density/quality/buyers R35/
  report_data/compare）——报告已到十一节
- src/pipeline/（runner + pipeline_runs 台账 + 增量水位）
- main.py 子命令：collect/extract/analyze/report/templates/db/pipeline
- docs/PYTHON-BOUNDARY.md：每新增模块必须登记（§2 表+docstring 非生产标注）

## 下一步
1. R39-R41（SVG 图/模板/JSON 落盘）完成批次 H
2. R42-R45 管道运维批；R46-R51 抽取质量批；R52-R60 收口批
3. R60 归档轮：更新 Codeberg PR #2 或新开迭代二段 PR + 交付说明

---

# 会话三段（2026-11-10 下午）——迁移 git.mingjiu.store + issue 驱动五连

## 平台切换（负一章）
- GitHub 停用实锤；Codeberg **不再直接推**（用户已在自部署 Forgejo 建好
  镜像 + 每 2 分钟同步 main 到 Codeberg/CNB——反向推会被覆盖）
- 唯一提交入口：https://git.mingjiu.store（sandbox 组织，HTTPS+token）
- 新协作规则已入库：服务器 main AGENTS.md 负一章（agent-lead 写）——
  分支必须带身份前缀 `<身份>/<issue号>-<描述>`；PR 走 API（POST pulls）；
  PR 描述必须写本地验证；红线：不推 main / 不推 Codeberg/CNB / token 不入库

## 本轮完成（5 issue / 5 分支 / 5 PR，全部已推服务器）
- **PR #27** ← `agent-hd2k4/23-spill-unpack`：#23 P0 大文件打不开——
  materializeBigResult 解包 spill 完整响应壳（ipc.rs::spill_if_large 落盘
  {id,ok,result}，旧代码写 result.payload 无人读）→ >1.5MB 文件全开不了。
  测试 spill-unpack.test.mjs（行为级切片沙箱 4 + 静态 2）
- **PR #33** ← `agent-hd2k4/24-docx-highlight-none`：#24 DOCX 整页黄——
  三处叠加（解析存 none/映射兜底黄/调用无条件上色）全修；3938 处 none 零
  样式 / 2 处真 yellow 保持。测试 docx-highlight.test.mjs（真实招标 DOCX
  全量 3940 处逐个真跑 readRunFmt+highlightColor）
- **PR #36** ← `agent-hd2k4/25-pdf-default-100`：#25 PDF 打开 285%——
  默认 fitMode 'fit-width'→'free' + applyFit free 早退（issue 要求最小
  改动）；rotate/setZoom/onHostResize 语义全部锚定防误删
- **PR #41** ← `agent-hd2k4/19-bid-project-wizard`：#19 建项/导入向导——
  壳侧 bid.create_project（空工作区无中生有 + 缺省 external_key
  shell::ws::name 幂等 + lock(cache).take() 缓存失效）/ bid.import_tender
  （壳侧收编：工作区外绝对路径拷 tender-src/ 同名 -N 不覆盖；..词法预拒；
  filename 净化）；UI 空态引导卡两步向导 + 演示桥；selftest +7 检；
  bid.rs 单测 +2；测试 bid-project-wizard.test.mjs 29/29
- **PR #43** ← `agent-hd2k4/20-governance-exits`：#20 治理出口三件
  （**stacked on #41——合并顺序 #41 → #43**）——bid.packages 只读/
  bid.matrix_override（receipt 宿主四重绑定签域）/ bid.recover_state
  （三重域层约束）；UI：矩阵行裁定表单/VALIDATING 恢复引导卡/分包
  第六页签；**顺手修预存断链**：renderBidMatrixPanel 工作台单参路由
  panel=undefined TypeError（#21 活例）；测试 bid-governance-exits 30/30

## 基础设施成果（本轮最有长期价值的部分）
1. **沙箱 Rust 工具链恢复**：rustup 安装 OK；bidcore 依赖 github/mmqz/
   mdcore（被 suspended 不可达）→ `git config --global url."https://
   sandbox-agent:<TOKEN>@git.mingjiu.store/sandbox/mdcore".insteadOf
   "https://github.com/mmqz/mdcore"` + `~/.cargo/config.toml` 加
   `[net] git-fetch-with-cli = true`——rev f4328eb 在服务器 mdcore 可达
   （SHA fetch 已开）。纯逻辑 crate（bid-mcp/bid-tools/bid-domain）
   `cargo check` 全绿（1m11s）
2. **mang-app 壳在 Linux 沙箱不可编译**（tao/wry 需 gtk/webkit 系统库，
   无 root 装不了）→ 四层降险体系：
   a. 新函数逐字复刻既有模式（gate_pass/state 同构）
   b. `scripts/bidcheck` mini-crate（**不入库**）：新函数真源粘贴 + 真实
      bid-mcp/bid-tools 依赖编译 + 行为冒烟（真实工具面全链：建项幂等/
      真实招标 DOCX 收编/守门拒绝/防御面）——cargo test 2 passed
   c. rustfmt 全文件解析（语法门）+ 新段净增 diff=0 对齐存量基线
   d. Rust 单测/selftest 随代码提交，Windows 真机跑
3. **验证套件全绿**：web-ui run-all.mjs 8/8（新增 spill-unpack/
   docx-highlight/pdf-default-zoom/bid-project-wizard/bid-governance-exits
   五个测试文件）；esbuild 构建 OK；pytest 面未动

## 服务器现况
- 分支：backup/*（迁移批）+ feat/601* + agent-ww4y/*（**另一 agent，
  认领了 #18/#16——勿动其 issue**）+ agent-lead/*（平台文档）+ 本轮
  agent-hd2k4/* 5 条 + fix/584 + feat/601-iterate（R31-R38 已推服务器）
- open PR：#27 #33 #36 #41 #43（我方）+ #15 已合并（agent-lead 文档）
- open issues 剩余：#21（五面板 e2e 骨架——重基建，下轮主菜）/ #18 #16
  （agent-ww4y 认领）/ mdcore 仓 17 个（另一产品线）

## 下轮入口
1. 看 Lead 合并情况处理 PR 反馈；#41/#43 stacked 顺序提醒已在 PR 描述
2. **#21 e2e 骨架**：以 IPC-CONTRACT 无窗口跑清单为起点建 UI 驱动 e2e
   （真实/仿真宿主二选一先立骨架）；gates 全链已有真跑测试可复用
3. Windows 真机验收清单（各 PR 描述里的待复核项）：645KB PDF 65 页/
   DOCX 无黄底/100% 缩放/向导点击流/裁定-恢复-分包点击流/selftest 62+7
4. 沙箱重置后恢复：PATH 加 ~/.cargo/bin；git url insteadOf 已在
   global config（沙箱重置会丢——重配命令见上）；npm install esbuild
   typescript（web-ui）装验证工具链

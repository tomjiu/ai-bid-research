# #603 治理面长期线 · 第 1 轮交付状态（2026-11-09）

> Agent-603a · 分支 `feat/603a-bid-gates` · commit `6ef2c25` · base = main @ `347e0c1`

## 本轮交付（30 轮长期线的第 1 轮）

**主线选定**：标书工作台「治理面」——#313 四面板解决了「用户无法自己检查」，
本线开「无法干预」半场。母 issue **#603**（P1）已建于仓库，批次计划 A-H：

| 批 | 内容 | 状态 |
|---|---|---|
| **A** | 审核门面板 + bid.gates / bid.gate_pass（宿主签发 receipt） | ✅ 本轮完成（本地） |
| B | 否决死锁人工豁免（set_matrix_override + 矩阵面板入口） | 待做 |
| C | 补遗豁免（record_addendum_waiver 逐件 + confirm_no_addendum 全局） | 待做 |
| D | 拒审修订流（RT 台账/派生/推进/章节重开） | 待做 |
| E | 版本面（save_version + 版本间差异） | 待做 |
| F | 导出前确认闭环 | 待做 |
| G | 数据活性（db.json 变更 → 面板自动刷新） | 待做 |
| H+ | 锚点互跳/响应式/i18n 打磨 | 待做 |

**批 A 范围**（7 文件 +1287/-5，已提交本地）：
- `bidcore/crates/mang-app/src/bid.rs`：bid.gates（DomainStore 直读五门台账）+ bid.gate_pass（#182 宿主签发 receipt → record_review_gate 真实工具面）+ 单测 ×3
- `bidcore/crates/mang-app/src/ipc.rs`：两命令注册
- `bidcore/crates/mang-app/src/selftest.rs`：+5 检查项
- `web-ui/mang/app.js`：审核门页签 + 追认清单 + 过门/拒审表单 + 演示桥可变 stub
- `web-ui/mang/styles.css`：面板样式 + 响应式（1440/1920）
- `web-ui/tests/bid-panels.test.mjs`：+28 检查项（**本机真跑 94/0 全绿**）
- `docs/mang/IPC-CONTRACT.md`：两命令契约登记

## ⚠️ 硬阻塞：GitHub 账号被封禁

开发期间（2026-11-09 ~09:20 UTC 后）token 账号（mmqz PAT）被 GitHub 封禁：

- API 全面 403：「Sorry. Your account was suspended」
- git push 403：「remote: Your account is suspended」
- **已完成的远端动作**：issue #603 创建成功 + 正文修复成功（封禁前几分钟）
- **失败的远端动作**：#603/#310 认领评论、分支推送、PR 创建——全部 403

处置：全部本地完成，重放套件已备好。

## 通道恢复后的一键重放

```bash
# 解封或换新 token 后（token 写入 /home/z/my-project/.ghtoken）：
python3 /home/z/my-project/scripts/replay_603.py
```

脚本幂等：push 分支 → 建 PR（base=main）→ 补认领评论 → #310 登记。
PR body 已写好（含「通道封禁期间提交」的通道备注）。

## 纪律执行情况

- ✅ 对标 main 开分支（origin/main @ 347e0c1，封禁前最后验证）
- ✅ 提交前 `git diff origin/main` 校验（7 文件 +1287/-5，零越界）
- ✅ 冲突标记零残留扫描（0.0.9）
- ✅ 不碰 PR #600（批 D 覆盖报告页签），冲突留 Lead 裁决
- ✅ 域层/工具层零改动（纯接线，单一真源）
- ⚠️ 提交前 fetch 复查被同一封禁阻断——若 main 已前进，PR 时需 Lead 裁决 rebase
- ⏸️ 不合并（PR 提交后等 Lead 审核）

## 环境如实声明

本沙箱无 cargo/rustc——Rust 面未本地编译（静态核对 + CI 兜底，与 #596/#597
先例同口径）；web-ui 面本机 node 24 真跑全绿（bid-panels 94/0 + run-all 6/6）。

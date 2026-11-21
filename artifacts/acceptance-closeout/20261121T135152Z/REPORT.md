# 本地验收收官报告（#115 · 独立入口）

- 生成：2026-11-21T13:51:57+00:00（mode=strict）
- 仓库：10ec81b25185 @ main（dirty 45 文件）

| 分栏 | 裁定 | 关键事实 |
|---|---|---|
| songling67 | **BLOCKED** | 金标准16条 needle 召回 16/16；层2缺料 5 项 |
| multifile | **PASS** | 淮安项目 4/4 件在位；补遗件=False |
| realagent | **NOT_RUN** | env 门 ws=unset phase=unset |
| baseline | **SKIP** | exit=None all_pass=None 用时Nones |

## 总裁定：FAIL

阻断原因（严格模式——跳过核心门不得宣称收官）：
- songling67: BLOCKED —— 层2素材 5 项 MISSING（67 条本体面缺料——#112 如实口径）
- realagent: NOT_RUN —— 真实 LLM 通路未执行（BID_REAL_PATH_WS/PHASE 未设；run_real_llm_path.sh 两相位人工中继是 #113 的登记边界）
- baseline: SKIP —— --skip-baseline

## 重放

```bash
git -C /home/z/my-project/ai-bid-research rev-parse HEAD  # 20261121T135152Z
/home/z/.venv/bin/python3 scripts/acceptance_closeout.py --skip-baseline
```

结果协议：/home/z/my-project/ai-bid-research/artifacts/acceptance-closeout/20261121T135152Z/result.json（schema v1）
日志：/home/z/my-project/ai-bid-research/artifacts/acceptance-closeout/20261121T135152Z/run.log（密钥形已脱敏：token/password/secret/api-key 形 + URL basic-auth）
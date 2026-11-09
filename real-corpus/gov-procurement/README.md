# real-corpus/gov-procurement — 政府采购真实语料库（M1.7 · S2 批次一）

## 口径声明（先读）

1. **公开与溯源**：本目录全部输入为依法公开的政府采购公告信息（发布平台：中国政府采购网
   www.ccgp.gov.cn，法定公开渠道）。每份文件保留：来源 URL、发布日期、抓取时间、sha256。
   语料为评测用途引用公开公告原文；不重新分发付费数据库内容。
2. **公告级 ≠ 文件级**：目录主体为公告级文本（含更正公告中逐条引用的招标文件条款原文，
   构成真实条款级配对）。招标文件**本体**（ccgp 中标公告附件 pdf）受 WAF 阻断未获取，
   登记为待人工项（`gt/ground-truth-draft.jsonl` GT-M17-24）——公告级验证不得宣称为文件级验收。
3. **GT 为初标草案**：`gt/ground-truth-draft.jsonl` 24 条全部 `draft_pending_human`，
   人工冻结前相关准确率仅作探索性指标（EXPLORATORY）。

## 目录结构

```
files/       链节点公告文本（# 头部含 URL/Type/Publish/sha256 由报告计算）
             cuc-028-tender-20260713.txt      招标公告（节点1）
             cuc-028-correction-20260728.txt  更正公告（节点2，条款级原文↔更正后配对）
             cuc-028-award-20260814.txt       中标公告（节点3，含附件清单）
sources/     官方镜像 HTML 字节级存档（cuc.edu.cn，第二独立官方来源交叉校验用）
gt/          ground-truth-draft.jsonl（M1.7-C 初标草案 24 条）
artifacts/   real-chain-report.json（验证报告：逐断言 + 溯源）
inventory.json / chains.json / stats.json   M1.7-A 盘点（576 份官方公告存档溯源清单）
```

## 使用（每轮测试入口已集成）

```
python3 scripts/m17_inventory.py     # 重建溯源清单（只读外部存档，不写外部仓库）
python3 scripts/m17_real_chain.py    # M1.7-B 真实链验证（34 断言，退出码 0/1）
python3 scripts/run_tests.py         # 全量回归（T14 = M1.7 真实链 + 盘点在案检查）
```

## 链全景（cuc-028：中国传媒大学教学资源中心建设）

| 节点 | 日期 | 角色 | 官方 URL |
|---|---|---|---|
| 招标公告 | 2026-07-13 | 原始条款基准（预算 108 万/开标 08-03/综合评分法/面向中小企业） | cggg/zygg/gkzb/202607/t20260713_26925801.htm |
| 更正公告 | 2026-07-28 | 3 真实 MODIFY（开标 08-03→08-13；进度节点1 07-31→08-30；节点2 08-30→09-10）+ 2 真实不变陷阱 +「其他内容均无修改」影响面声明 | cggg/zygg/gzgg/202607/t20260728_27025731.htm |
| 中标公告 | 2026-08-14 | 输出复验基准（知途教育 105 万≤108 万/89.36 分/08-14≥08-13）+ 附件清单（更正后招标文件 pdf 待人工获取） | cggg/zygg/zbgg/202608/t20260814_27133532.htm |

## 数据来源说明

- 576 份存量公告存档：源自外部参考仓库 `tlyyxjz__BidAgent`（GOAI 参赛项目）的
  `_w3/_w4/_w5_raw` 抓取存档（只读使用，未向其写入）。公告本体为 ccgp 公开信息。
- cuc-028 三节点：ccgp 官方文本 + cuc.edu.cn 官方镜像（HTML 字节存档，交叉校验锚点全命中）。
- inventory 中 6 份公告缺正文（抓取存档本身为空），已在 parse_flags 标注，不入验证。

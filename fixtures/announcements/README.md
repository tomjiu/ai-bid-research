# 合成公告语料（#601 研究管道 fixtures）

> **定性：完全合成的脱敏样例数据集——非真实语料。**
> 与 `real-tender-*` / `songling-*` 真实语料严格分离；不含任何真实项目
> 编号、采购人、供应商与金额。形态上覆盖中国政采公告的常见写法
> （编号/金额单位/日期格式/资格小节），供研究管道的离线演示与测试。

## 布局

```
structured/   结构化源（collect 阶段输入）
  a-zhejiang.json    JSON 数组：浙江省 3 件（含中文别名键/亿元金额/中文日期）
  b-beijing.jsonl    JSONL：北京市 3 件（含同 URL 多源重复件——去重面用例）
  c-update.json      单对象：a-zhejiang.json 中 ZJ-SYN-2026-001 的更新件
                     （bid_id 命中 → 增量水位 update 用例）
raw/          公告原文源（extract 阶段输入）
  hlj-smartcity.txt  规则抽取可完整命中样例（编号/金额/日期/资格全形态）
  zj-cloud.txt       简形态样例（部分字段缺失——诚实降级用例）
  noise.txt          非公告文本（抽取失败 → raw 暂存 pending 用例）
```

## 用法（#601 批次 D 验收口径）

```bash
python main.py pipeline \
  --announcements fixtures/announcements/structured \
  --raw-texts fixtures/announcements/raw \
  --db /tmp/demo.db --output-dir /tmp/demo-reports
# 离线产出含统计数字的 Markdown 报告（无 LLM、无网络）

python main.py pipeline \
  --announcements fixtures/announcements/structured \
  --raw-texts fixtures/announcements/raw \
  --db /tmp/demo.db --output-dir /tmp/demo-reports --dry-run
# 全链预演：零副作用
```

## 维护纪律

- 合成数据**不承诺**任何分布代表性（区域/金额/类别均为手工编排）；
- 新增字段形态用例时同步更新本 README 的布局清单；
- 该目录服务于 Python 研究工具链（PYTHON-BOUNDARY.md 选项 A 定性），
  不进 Rust bid 链路的任何测试。

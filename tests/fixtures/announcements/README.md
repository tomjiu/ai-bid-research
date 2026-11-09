# 合成公告 fixture 数据集（#601 端到端测试源）

> **口径：合成脱敏数据，非真实语料。** 覆盖研究管道全部特性面；
> 消费方：`tests/test_e2e_pipeline.py`（离线全链断言）。
> 真实语料走 `bidcore` 的 corpus 面（与本 fixture 无关，见
> `docs/PYTHON-BOUNDARY.md`）。

## 文件清单与覆盖面

| 文件 | 形态 | 覆盖面 |
|---|---|---|
| `a-别名与重复.json` | JSON 数组 ×3 | 中文别名归一（招标编号/预算金额/年月日）；同件重复（`FX-001` 双源）；千分位金额 `3,500万元` → 3500.0 |
| `b-原文流.jsonl` | JSONL ×4（1 坏行） | 逐行装载 + 行级失败粒度（坏行只登记该行）；`content` 键原文流（LLM 抽取面）；空行容忍 |
| `c-单对象.json` | JSON 单对象 | 单对象形态；已定标（winner 非空） |
| `d-损坏.json` | 坏 JSON | 文件级失败登记（不殃及后续文件） |
| `e-缺字段.json` | 缺 project_name | 记录级校验失败（RecordValidationError → failures 明细） |
| `f-定标面.json` | JSON 数组 ×5 | 同词多项目（智慧水务×5——词表命中/密度/定标率统计面） |

## 分账预期（`test_e2e_pipeline.py` 对账口径）

```
files_read = 6          # 全部源文件进入读取
loaded     = 11         # 3(a) + 2(b 好行) + 1(c) + 5(f)
deduped    = 1          # FX-001 同件重复
new        = 10         # 去重后入库
failures   = 3          # d-损坏.json（文件级）+ b-原文流.jsonl:2（行级）+ e-缺字段.json（记录级）
```

## 扩展约定

- 新增 fixture 文件时同步更新本 README 的分账预期与
  `tests/test_e2e_pipeline.py::test_collect_stage_accounting` 断言；
- 命名规范：`<序号>-<覆盖面说明>.<json|jsonl>`——按文件名排序装载，
  前缀序号即装载序（确定性）；
- 合成数据保持脱敏：区域/采购人/代理用「某市某局」类占位词，
  禁止粘贴真实公告原文。

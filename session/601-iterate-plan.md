# #601 研究管道——迭代二段计划（R31-R60，feat/601-iterate 分支）

> 背景：GitHub 仓库被 suspended，issues 全部丢失；按用户指令依预存计划继续开发。
> 一段（R1-R30）已全部完成：29 commits 存档于 Codeberg PR #2（feat/601-extract）。
> 二段基线：feat/601-extract @ 224a29c；测试基线 305 绿 + 2 skip。
> 同步纪律：每轮 commit → push codeberg（has_actions=false 不触发 CI）；
> Codeberg 不通时 → `scripts/upload_fallback.sh` 上传压缩包到 temp.sh（3 天保留，免登录公开下载）兜底。
>
> **进度（2026-11-10 本轮会话）：R31-R38 已完成 8/30**，测试 305→389 绿 + 2 skip，
> 8 提交全部已推 codeberg feat/601-iterate。下一轮从 R39 起。
> 经验：同消息内 Edit 与 Bash 会并行竞态——改文件与跑测试必须分消息串行。

## 批次划分（30 轮）

| 批次 | 轮次 | 主题 | 内容 | 状态 |
|---|---|---|---|---|
| G 源面扩展 | R31 | CSV 源读取器 | .csv 表头→payload 映射、行级失败粒度、collect 分发扩展 | ✅ 7c029ce |
| | R32 | 源分发注册面 | 读取器表驱动注册 + register_source_reader 扩展点 | ✅ c02c4c2 |
| | R33 | 数据健全性规则 | 日期倒挂/长周期/未来发布/零预算——告警不拒收 | ✅ a5eda48 |
| | R34 | db export 导出面 | bids 研究快照导出 CSV/JSON + 过滤 | ✅ 3801a4f |
| H 分析深化 | R35 | 采购人画像 | top 采购人预算/频次/领域画像报告八节 | ✅ 9272366 |
| | R36 | 预算×区域交叉表 | 五档分桶稠密矩阵 + 报告九节 | ✅ 5081da7 |
| | R37 | 术语演化 | 关键词月度命中趋势（新兴领域信号）报告十节 | ✅ 169710d |
| | R38 | 集中度趋势 | 逐月 HHI/定标率序列 报告十一节 | ✅ c5a756d |
| | R39 | 报告 SVG 图 | 标准库生成柱状/折线 SVG 嵌入 HTML 报告（零新依赖）| ⬜ |
| | R40 | 报告模板面 | --template minimal/full 精简版 | ⬜ |
| | R41 | 分析 JSON 落盘 | --json payload 导出供外部工具复用 | ⬜ |
| I 管道运维 | R42 | pipeline --stages | 阶段选择器（只跑指定阶段）| ⬜ |
| | R43 | 运行摘要 JSON | 机器可读 run 报告落盘 | ⬜ |
| | R44 | runs-diff 对比 | 两次运行间新增/更新公告对比（db 子命令）| ⬜ |
| | R45 | TOML 配置 profile | stdlib tomllib 默认参数装载 | ⬜ |
| J 抽取质量 | R46 | few-shot 提示词 | bid_extraction 示例段注入（离线格式校验）| ⬜ |
| | R47 | 抽取差异面 | LLM 补全 vs 源字段 diff 报告 | ⬜ |
| | R48 | token 用量台账 | LLM 调用用量记录 + db 可见 | ⬜ |
| | R49 | retry 退避续跑 | pending 重试节奏控制 + 部分成功增量续跑 | ⬜ |
| | R50 | 失败原因聚合 | pending error 分类统计面 | ⬜ |
| | R51 | 双模板对照 | A/B 抽取一致性检查（离线直通可测）| ⬜ |
| K 收口 | R52 | 性能护栏扩面 | CSV 大源 + 新分析面护栏 | ⬜ |
| | R53 | fixture 扩充 | CSV fixture + 边界案例 + 契约 README 更新 | ⬜ |
| | R54 | CLI 冒烟扩面 | 12+ 项全链演练 | ⬜ |
| | R55 | 全链文档 | README 使用面 + PYTHON-BOUNDARY 登记新面 | ⬜ |
| | R56 | 卫生自查 | 未用 import 清零、标注一致性 | ⬜ |
| | R57 | 趋势专项报告 | analyze --trend 月度趋势独立子模式 | ⬜ |
| | R58 | 报告索引面 | output/ 最近 N 份报告导航索引页 | ⬜ |
| | R59 | 终验轮 | 全量测试 + 冒烟 + 台账对账 | ⬜ |
| | R60 | 归档轮 | 计划终态更新 + Codeberg 交付说明 | ⬜ |

## 纪律（继承一段）

- 每轮：实现 + 测试 + `feat(#601): R<轮次> <标题>` commit（Co-Authored-By: Agent-hd2k4）+ push codeberg
- PYTHON-BOUNDARY：新增模块/命令必须同步登记（§2 表 + docstring「非生产链路——仅供研究」）
- 纯标准库零新依赖；离线可测；启发式口径报告明示「估算」

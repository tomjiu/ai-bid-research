# 松岭复验脚本跨平台重放手册（#156 收口）

> 适用：`scripts/repro_112.py`（#112 松岭 67 关键点机器面）与
> `scripts/m145_repro.py`（m145 圈号子项块归属复现）。
> 2026-11-13 重做：GBK locale 崩启动、作者 Linux 绝对路径写死、固定共用
> workspace、失败裸 assert——四根因全部收口。基线 `5d1ad697`。

## 一条命令重放（双平台同形）

```bash
# Linux / macOS
python3 scripts/repro_112.py <ws> <out.json> [bid-mcp-stdio 路径]

# Windows（cp936 默认——无需 -X utf8，脚本内部全 IO 显式 UTF8）
python scripts/repro_112.py <ws> <out.json> [bid-mcp-stdio.exe 路径]
```

参数化（两脚本同款纪律）：

| 参数 | 位置参数 | 长选项 | 默认 |
|---|---|---|---|
| 工作区 | 第 1 个 | `--workspace`（repro_112）/ `--ws`（m145） | 无默认（m145 旧 `/tmp` 缺省已收口为平台临时目录） |
| 报告落盘 | 第 2 个 | `--out` | **必填**——报告不留盘等于不可重放 |
| 工具二进制 | 第 3 个 | `--bin` | 仓内 `bidcore/target/debug/bid-mcp-stdio`（**root 从脚本位置取得**；Windows 自动补 `.exe`） |
| 仓库根 | — | `--root`（m145） | 脚本位置上溯（不再写死 `/home/z/...`） |

## 重放纪律（脚本内建强制，不靠自觉）

1. **全 IO 显式 UTF-8**：`open(..., encoding="utf-8")` 与
   `subprocess.run(..., encoding="utf-8", errors="replace")`——不依赖
   系统 locale。Windows cp936 下读 UTF-8 金标准 JSON 不再
   `UnicodeDecodeError` 崩启动（issue #156 实测证据：0x81 孤字节）。
2. **工作区唯一或验证为空**：非空工作区 → 立即 `exit 1`（报旧数据项数）——
   不静默复用旧数据、不固定共用 workspace。复跑 = 新目录或先清空。
3. **失败非零退出（双闸）**：工具链任一步失败 = 回执 `ok:false` **或子进程
   退出码非零**（回执曾称 ok:true 也不放行——以退出码为准，回执原样保留
   附 `failure_reason`）；二进制不在位 / 金标准缺失 / 召回 < 16/16 →
   `exit 1` 且 stderr 附失败摘要（可诊断，不裸 assert 崩）。
4. **证据留痕**（repro_112 报盘字段）：`repo_head`（git SHA）、
   `tool.sha256`（bid-mcp-stdio 二进制指纹）、`pdf_sha256`（PDF 原件指纹）、
   `parse_channel_signal`（**只认本次实跑的导入回执 / db files 解析摘要**
   ——stderr 关键词只作 fallback 信号登记，失败 probe 的 pdfium 字样不
   采信为成功通道；证据不明记 `unknown`，报盘另留
   `parse_channel_source` / `parse_channel_fallback_signal`）。
5. **平台 exe 后缀**：Windows 下无后缀 bin 路径不存在时自动探测 `.exe`
   同伴（`--bin` 显式指定优先）。

## 基线口径（防误读——issue #156 验收原文要求「报告明确区分」）

- **16/16 检索/分类匹配 ≠ 完整语义保真**：金标准 needle 是 OR 检索锚
  （任一命中即召回）+ 分类一致——单位、上下限、页码与全文语义的核对归
  人工复核（金标准 `statement` 全文才是语义真源）。召回 16/16 不得表述为
  「语义保真 16/16」。
- **67 条原始材料仍未取得**（manifest MISSING 5 项）：召回面 16/16 不得
  抵充材料面——两条独立口径，报盘 `caveats` 字段固化此警示。
- **通道不预设、以实跑证据为准**：每次重放的解析通道从导入回执/db
  解析摘要取证（无证据记 `unknown`——不冒充）；PR #146 的 Poppler 318REQ
  是作者研究链口径——通道间数字不可互充基线、不可直接比对。跨通道
  一致性是独立课题（未做）。
- **m145「614-616 应无 REQ」是修复前口径**：那是 GR-004 漏抽缺陷的
  复现预期；PR #148 修复后圈号子项段落一致开条款。现脚本为**观测面**
  （逐块登记 req_ids/verdict/text，一致性由人对照 #148 修复说明判读），
  不再内嵌「应无」断言。

## 回归

`tests/test_repro_112_cross_platform.py`（17 例——参数化/UTF8 受控红绿/
安全复跑/失败非零/口径警示源面断言）。Rust 真链（create→import→extract）
与 Windows cp936 真机复验归 Lead 独立验收——Linux 实测不冒充 Windows 真测。

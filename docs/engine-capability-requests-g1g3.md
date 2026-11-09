# 引擎能力需求提交材料：G1/G2/G3（P0 差距 · 2026-10-25 核实版）

> **用途**：经用户转达引擎团队的正式需求材料。所有"引擎原文"均为**源码锚点直引**（非转述）。
> **核实基线**：`mmqz/mdcore` main = `c33bcab`（2026-10-25 快照同步；上次审计基线 6daeace 之后的新提交集中于壳/web/打包面——`git diff --stat 6daeace..c33bcab` 无 office-io 触及，本材料的 G1/G2/G3 代码锚点已逐条在 c33bcab 复核，**全部仍然有效**）。
> **责任边界**（AD-07）：文档引擎管通用文档能力（域/样式/元数据的通用实现）；标书侧管采购规则（条款解释、暗标口径断言、业务验收）。本材料只提通用能力需求，不含任何采购业务逻辑。
> **业务侧现状**：G1 域路径可行性已业务验证（fldChar 三连先例）；G3 业务侧 zip 补丁为**过渡缓解**（V1-d 金丝雀绿），引擎导出面产品化仍是暗标红线的终态。

---

## G1 · 目录（TOC）域写面 —— P0

**标书场景**：投标文件必须有自动目录（多级 + 页码）；目录域是评标检查格式项。

**引擎原文**（crates/office-io/src/docx.rs:2162-2163，c33bcab 直引）：

> 简单域代码（docx-r2 写面）：PAGE / NUMPAGES 两面（引擎元素族
> 其余域 = TOC[文档级]/PAGEREF[书签面]/HYPERLINK[`todo!()` 崩溃面

（写面注释 docx.rs:191 同源：`旋转图片、表格样式、TOC/PAGEREF/HYPERLINK 域、目录、`——登记不暴露清单。）

**现状语义**：PAGE/NUMPAGES 已用 fldChar begin/instrText/end 三连实现（`RunSpec::field_num_pages`，docx.rs:48/2242-2243：`Some = 本 run 展开为 fldChar begin/instrText/fldChar end 三连——无缓存结果文本：域值是渲染期计算面`）；TOC/PAGEREF/HYPERLINK 走 docx-r2 的 `todo!()` 崩溃面。

**需求（验收条件）**：
1. 写面暴露 TOC 域（文档级：`TOC \o "1-3" \h \z \u` 类指令），落位后结构读回可断言 fldChar 三连存在；
2. PAGEREF 域（书签面）写面可用——与既有 `bookmark_paragraph` 锚点写面（office-g Phase 1+2）衔接，使"引用条款→书签→目录页码"链路引擎内闭环；
3. 渲染级验收：LO headless 打开导出件，目录条目与页码域实际展开（业务侧已有同构先例可对齐：corpus-A 明标样本以 fldChar 三连落位 PAGE/NUMPAGES，LO 渲染 8 页硬断言全过——见 ai-bid-research artifacts/v1）；
4. 崩溃面收口：`todo!()` 替换为显式 `Err` 或实现（todo 崩溃对上层导出是 DoS 面）。

**依赖**：PAGEREF 依赖书签写面（已有）；TOC 无新增依赖（域指令即文本）；多级目录的 Heading 样式依赖 G2 的文档级样式面。

---

## G2 · 文档级格式面（默认样式/页边距/行距） —— P0

**标书场景**：招标格式硬要求——页边距（如上 2.5cm 下 2.5cm 左 3.0cm 右 2.5cm 型）、正文字体字号（宋体/仿宋族）、行距（如 1.5 倍/固定值 28pt）、封面页。

**引擎原文**（crates/office-io/src/docx.rs:167-168，c33bcab 直引）：

> - 节属性（page size/margin 等——页眉页脚引用面已暴露，其余
>   节语义面外）；

（补充直引 docx.rs:174-175：`行内 rFonts/strike/underline 与段落边框 pBdr 读面不承载`。）

**现状语义**：节属性的页眉页脚引用面已暴露（section_property.header/first_header/even_header/footer/…，docx.rs:2540-2600 槽位写面）；page size/margin 等其余节语义"面外"。全仓无 `spacing`/`docDefaults`/`styles.xml` 文档级样式 API（c33bcab 全文检索零命中）。

**需求（验收条件）**：
1. 节属性写面暴露 page margin（w:pgMar 四边）——读回可断言；
2. 文档默认样式写面（styles.xml docDefaults 或等价抽象）：正文默认字体族（中文字体名）、字号、行距（w:spacing w:line/w:lineRule）；
3. 读面最低限度：margin 与默认行距可读回（供业务侧格式自检断言）；
4. 渲染级验收：LO headless 打开后版式实测（边距量级 + 行距量级）。

**依赖**：无新依赖（OOXML 标准节）。与 G1 的多级目录样式（TOC 1/2/3）衔接。

---

## G3 · 暗标元数据清零 —— P0（R-11 BLOCKER）

**标书场景**：暗标废标红线——导出件 docProps 不得含作者/公司/最后修改者（评标现场查 docProps/core.xml 与 app.xml；检出即废标）。

**引擎原文**（检索证据，c33bcab）：全仓检索 `docProps|creator|lastModifiedBy|Company` 在 crates/office-io/src/ 下**零命中**——无 docProps 清零面；既有 `ExportClean` 是证据侧干净导出，非暗标格式能力。

**业务侧现状**（过渡缓解已验，V1-d）：zip 层补丁清零 core.xml creator/lastModifiedBy + 移除 app.xml Company + LO 产出 PDF author 空；金丝雀防空洞断言（明标件必须被检出的扫描器有效性证明）全绿。**zip 补丁绕过了引擎的原子发布面**——元数据不再受引擎指纹/门禁保护，这是过渡方案的结构性缺陷。

**需求（验收条件）**：
1. 导出面提供"匿名模式"（或等价能力）：导出时 docProps/core.xml 的 creator/lastModifiedBy 置空、app.xml Company 移除（保留修改时间戳的可配置策略——部分地区评标查时间戳连续性）；
2. 落库指纹口径：匿名导出的 sha256 稳定（同输入同匿名配置 → 同字节）——保持原子发布/幂等语义；
3. 渲染级验收：匿名导出件 LO/PDF 产出 author 为空；金丝雀断言由业务侧提供（不塞给引擎）；
4. **与 ExportClean 的关系澄清**：ExportClean 是证据导出的干净链路面（引擎原语义保留），暗标匿名是格式面新能力——两者不合并。

**依赖**：无新依赖；与既有原子发布（tmp+rename+sha256 落库）衔接——匿名转换必须在发布边界内完成（不得先发布再补丁，否则破坏"EXPORTED ⟺ sha256 落库"不变式的字节语义）。

---

## 附：核实记录与不成立项

| 项 | 核实方式 | 结果 |
|---|---|---|
| mdcore 新提交是否触及 G1/G2/G3 面 | `git diff --stat 6daeace..c33bcab` 过滤 office-io/docx | 无触及（新提交 = s5a-env/s5b 壳/deb 打包/p6 web 面组合套件） |
| G1 todo!() 面 | docx.rs:2162-2163 直读 | 仍然成立（TOC/PAGEREF/HYPERLINK 不暴露） |
| G2 样式/行距 API | 全文检索 spacing/docDefaults/styles.xml | 零命中（不存在） |
| G3 docProps 面 | 全文检索 docProps/creator/lastModifiedBy/Company | 零命中（不存在） |
| cleanroom-analysis | 同步至 f9efe19（s5c-host10 判定——与本三缺口无交集） | 无影响 |

**提交方式**：本材料经用户转达引擎团队（引擎仓只读红线不破——不向 mdcore 提 issue/commit；需求变更走用户中转，状态回填 doc-engine-audit.md §4/§6 与 AD-07）。

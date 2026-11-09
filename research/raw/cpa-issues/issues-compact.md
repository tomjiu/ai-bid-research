## #1 qoder 国际版回调不对
[closed] 评论 0 条
正文: qoder 国际版回调不对，回调去qoder://aicoding.aicoding-agent/login-success了

<img width="559" height="225" alt="Image" src="https://github.com/user-attachments/assets/49556017-35bd-459d-9d7d-570362a06206" />

## #2 启用trae就报错
[closed] 评论 0 条
正文: 使用了workbuddy和trae，单独禁用trae能正常在cc里面请求（不知道为什么能看到思考，无法接收到回复）
启用trae后就一直报错，尝试了cli和docker的cpa都这样，都用了最新版本
```[2026-09-05 19:13:53] [--------] [warn ] [scheduler.go:68] pluginhost: scheduler rejected auth pick plugin_id=trae error=unknown method: scheduler.pick
[2026-09-05 19:13:53] [9f7ad37e] [error] [gin_logger.go:93] 500 |           7ms |    192.168.32.1 | POST    "/v1/chat/completions"
[2026-09-05 19:13:54] [--------] [warn ] [scheduler.go:68] pluginhost: scheduler rejected auth pick plugin_id=trae …[截断]

## #3 fix(workbuddy): rewriteSystemInPlace 未过滤消息角色且一刀切替换 >2000 字节内容导致多轮对话上下文丢失
[closed] 评论 0 条
正文: ### 问题描述 (Bug Description)

使用 `workbuddy` (CodeBuddy) 插件进行多轮对话或长文本交互时，模型频繁出现**“丢失上下文/严重失忆”**的情况，具体表现为：
1. **多轮对话失忆**：第一轮模型给出的代码或回复（超过 2000 字节时），第二轮向模型提问“针对上面的代码/内容做修改”时，模型表示“这是第一条消息，没看到任何代码/内容”；
2. **长 Prompt 丢失**：单次发送稍长的指令/背景/代码片段（> 2000 字节），模型完全无视提问，直接回复通用的问候语（如 "I'm ready to help with your software engineering tasks..."）。

---

### 根本原因定位 (Root Cause Analysis)

问题定位在 `plugins/workbuddy/payload.go` 中的 `rewriteSystemInPlace` 及 `sanitizeContentText`：

```go
const maxSystemPromptBytes = 2000
con …[截断]

## #5 feat(workbuddy): 支持多轮对话历史思考(reasoning_content)注入回放，避免上游静默丢弃导致模型失忆
[closed] 评论 0 条
正文: ### 背景与问题描述 (Background & Problem)

在使用 `workbuddy` 插件配合各类支持思考链的客户端（如 DeepSeek Harness, OpenCode/OMP, Claude Code, Cherry Studio 等）进行多轮对话时，存在**“上轮思考过程无法被下轮模型感知 / 记忆断裂”**的问题：

1. **下行流式表现正常**：`stream.go` 已完整支持将腾讯 SSE 中的思考内容提取并转换为标准 OpenAI `delta.reasoning_content`，客户端 UI 能够正常渲染出折叠的思考过程。
2. **上行回放出现断裂**：在多轮对话中，客户端根据 OpenAI 标准将上一轮 assistant 消息连带 `reasoning_content` 一并回传。然而，**腾讯 CodeBuddy 上游接口在服务端反序列化时，仅接受白名单字段（`role`, `content`, `tool_calls` 等），非标的 `reasoning_content` 被上游网关静默丢弃（Drop）**。
3. **底层模型表现 …[截断]

## #7 在我本机构建的darwin-amd64成功，放到CPA启动失败
[closed] 评论 0 条
正文: 错误原因大致是go编译的qoder插件和CPA的兼容问题，AI搞的没细看，正在用rust来搞。佬有能用darwin-amd64包吗？给发一个☺

## #8 fix(qoder): 动态模型列表请求签名无效(403 Signature invalid)，静默回退到过时静态模型表（缺 7 个模型）
[closed] 评论 1 条
正文: ## 现象

qoder 插件对外暴露的模型列表只有 **11 个写死的旧模型**，而 Qoder 上游 `chat` scene 实际有 **15 个可用模型**。缺的 7 个（`ultimate` / `performance` / `efficient` / `qmodel_38max` / `kmodel_latest` / `gmodel` / `gfmodel`）在宿主里直接调用会报：

```
400 {"message":"unknown provider for model gmodel","code":"model_not_found"}
```

另外列表里还留着 3 个上游已下线的旧 key（`qmodel_preview` / `q36fmodel` / `gm51model`），`kmodel`、`mmodel` 的 display_name 也是旧名字（Kimi-K2.7-Code / MiniMax-M2.7）。

## 根因

`plugins/qoder/models.go` 的 `callModelsAPI()` 用**空 body** 发 GET …[截断]
评论@wkler: 补充：同一个「过时」问题还有两处，我一起在本地修了（补丁附在下面）。

## 1. `body.go` 的 `cpaToUpstreamKey()` 别名表过时

表里还停在旧模型上，缺了上游新增的 7 个，而且旧名没更新：

| 现状 | 上游实际 |
|---|---|
| `glm-5.2` / `gm51model` → `gm51model` | GLM-5.3，key 已变成 `gmo …[截断]

## #9 trae cn 变体聊天全部 4001：llm_utils_chat 只接受 solo_work_lite，cn→inline_chat 映射是死路
[closed] 评论 0 条
正文: ## 现象

`cn` 变体（TRAE CN，OAuth client id `ono9krqynydwx5`）登录的凭据，对模型发现返回的**每一个**模型发起聊天都失败，HTTP 200、SSE 流内层报错：

```
aggregate: solo error code=4001 msg=We're sorry, the param is invalid. Please try with a valid param.
```

换请求形状（去 max_tokens / 强制 stream / `/v1/responses` 端点）无效；v0.12.51 与 v0.12.77（trae 0.12.54）行为一致，不是回归。

## 根因

`upstream/variant.go` 的 `functionByVariant` 把 `cn`/`intl` 映射为 `function: "inline_chat"`，聊天统一发 `POST /api/agent/v3/llm_utils_chat`（`upstream/constants.go:22`）。但该端点**只接受 `solo_ …[截断]

## #10 trae v0.12.55 起：solo_agent-only 前缀名单把实测可用的 DeepSeek-V4-*-Official 一起误杀了
[closed] 评论 1 条
正文: trae v0.12.55 起：solo_agent-only 前缀名单把实测可用的 DeepSeek-V4-*-Official 一起误杀了

## 背景

issue #9 的修复（`25ef77b`，v0.12.79）把 cn/intl 车道改到 `solo_work_lite`，同时加了 `soloAgentOnlyPrefixes` 过滤死模型。方向完全同意，但名单是**前缀匹配**：

```go
// plugins/trae/upstream/client.go:385（v0.12.82）
var soloAgentOnlyPrefixes = []string{"agnes", "deepseek-v4"}

func configIsSoloAgentOnly(configName string) bool {
	lower := strings.ToLower(configName)
	for _, p := range soloAgentOnlyPrefixes {
		if strings.HasPrefix(lower, p) {   // ← 这里
			 …[截断]
评论@mmqz: 感谢这份报告——表格里的对照实验（同机同凭据只换 dylib、可见数 20→13）把问题钉得很死，前缀匹配确实过宽了。

已按建议 1 修复（v0.12.83，trae 0.12.56）：

- `soloAgentOnlyPrefixes`（前缀）→ `soloAgentOnlyDeadNames`（精确 config_name 集合），只收当场验证过的死键：`deepseek-v4-flash …[截断]

## #12 workbuddy / qoder：流式路径的失败没有状态，宿主既不能降级也不会冷却（附 PR #11 同款改法）
[closed] 评论 3 条
正文: workbuddy / qoder：流式路径的失败没有状态，宿主既不能降级也不会冷却（附 PR #11 同款改法）

## 背景

我们在搭一条"同一个客户端模型名由多家供、按 codearts → trae → workbuddy → qoder 顺序降级"的链。CPA 只有在拿到**带 HTTP 状态的上游错误**时才会冷却凭据并换下一个（401/402/403/404/429/5xx 轮转，400/409/413/422 直接终止）。

今天两家（外加 trae，已在 PR #11 修好）的**异步流式**路径都做不到这一点：`handleExecStream` 先 `go pumpUpstreamStream(...)` 再 `return okEnvelope(headers)`，于是 pump 里所有失败都只能走 `host.stream.emit`，而那条 RPC 只有 `{"stream_id","error"}` 两个字段，宿主把它变成 `fmt.Errorf("%s", req.Error)`——**code 与 http_status 全丢**。客户端看到 `20 …[截断]
评论@mmqz: 这份分析非常扎实——pump 路径 `host.stream.emit` 只有 {stream_id, error} 两个字段、状态全丢，这个观察和两个插件的行号定位都对，感谢。逐条回答你的两个设计问题：

**1. 首包等待的期限放哪儿？**

- **(c) 宿主侧 `host.stream.emit` 支持 code/http_status 是架构上正确的终局方案**：一处改动四个插件受益， …[截断]
评论@mmqz: 更新与更正：

**1. 上游路线撤回。** 上一条答复里说过会在上游 CLIProxyAPI 提 `stream.emit` 状态透传的 issue + PR——这条路线搁置，不再向上游提案。(c) 降级为「如果上游未来自行支持 code/http_status，插件侧免费受益」；在那之前，插件侧把它当纯文本错误通道用。

**2. 复盘确认：插件侧能做的已经全部就位。** 复查主线后发现不必再 …[截断]

## #13 trae：SOLO 通道非流式请求必挂 4001（流式正常）；附带 4001→404 映射值得斟酌
[closed] 评论 2 条
正文: ### 现象（trae 0.12.56 / v0.12.83，SOLO 通道）

同一模型、同一凭据，客户端只差一个 `stream` 标志，结果稳定复现两种结局：

```bash
# 200，正常出话（重复 3 次全对）
curl -s localhost:8317/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"kimi-k3-solo","stream":true,"max_tokens":16,"messages":[{"role":"user","content":"收到"}]}'

# 必挂：三个 SOLO 凭据全部聚合失败
curl -s localhost:8317/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"kimi-k3-solo","s …[截断]
评论@mmqz: 两点都收到了：一点定案无需改动，另一点按你说的「两个入口各打一行」做成了实测工具，随 v0.12.85 发布。

---

## 1. 4001→404 映射：现状已经是你要的「请求级、不连坐账号」形态，404 根本不会到宿主

PR #11 落地时是两级配合的：`soloFaultStatus` 确实把 4001（ErrModelUnavailable）映射成 404，**但 `upstream …[截断]
评论@shadyrispy: 开关很好用,抓到了,而且结论跟我们俩的预期都不太一样——**先把最要紧的放在前面:这条 issue 的前提是错的,"非流式必挂 / 流式正常"的不对称在我现在的环境上复现不出来,两侧都 200。当时看到的整条 SOLO 通道 4001 是我自己造成的:我在宿主侧给三条凭据都加了模型 `prefix`,它漏进了出站 `config_name`。**细节我另开一个 issue,这里先把你们要的数据交上 …[截断]

## #16 trae OAuth回调失败
[closed] 评论 1 条
正文: trae OAuth回调 URL 提交失败: state is required  这个要怎么处理
评论@mmqz: ## 根因：粘贴框用错了，且这个错是「必然」的

`state is required` 来自宿主自己的通用端点 `POST /v0/management/oauth-callback`——你把链接贴进了 **CPA 管理界面 / TUI 的「回调 URL」粘贴框**。这个框对 trae 登录**永远不可能成功**，原因在 Trae 重定向的形态：

1. Trae 授权页硬性校验回调只能是 `h …[截断]

## #17 workbuddy国际版在cpa中看不到具体模型
[closed] 评论 1 条
正文: <img width="944" height="805" alt="Image" src="https://github.com/user-attachments/assets/9751de56-7390-4e5b-8c12-c5187493fc12" />
只能看到这几个，而且自动获取模型的时候无法被获取到
评论@mmqz: 已修复，随 v0.12.88 发布（workbuddy 0.9.35，f2bd862）。

根因：网关把 /v3/config 目录按客户端身份切分（IDE 与 CLI 各持一份花名册，官方口径 split is load-bearing），我们的模型探测此前只带 IDE 身份——国际版凭据于是只看到 IDE 名册里那几个产品档位别名 + o4-mini，自动获取模型自然一无所获。这不是你的凭据或 …[截断]

## #18 trae: 宿主的模型名前缀会漏进出站 config_name → SOLO 通道每条调用 4001(附 TRAE_DEBUG_PAYLOAD 证据)
[closed] 评论 1 条
正文: > 查重:`gh search issues --repo mmqz/cpa-multi-plugins prefix` 无结果;#10 讲的是 solo_agent-only **名单前缀误杀**,这条讲的是**宿主侧模型名前缀漏进出站 body**,是不同的接缝。诊断数据来自 #13 的那次抓包(同批日志)。

## 症状

给 trae 凭据配了宿主的模型名前缀之后(CPA 的 per-credential `prefix` + `force-model-prefix: true`,目的是让多家 provider 的同名底模在 `/v1/models` 里可区分),**这个前缀会出现在发往上游的请求体里**,于是 SOLO 通道每一条聊天调用都失败:

```text
aggregate: solo error code=4001 msg=We're sorry, the param is invalid.
```

流式/非流式都失败、三个账号都失败、0.7~1s 秒失败;而把凭据的 `prefix` 清空(其他一切不变)之后,19 个 `-solo` 模型里 15 个立刻恢复 …[截断]
评论@mmqz: 已修复，落在 main（6ec801e，trae 0.12.59），随下一个 release（按惯例为 v0.12.89）发出。在此之前维持你的规避（清空 prefix）或自建 main 构建，两者都热生效。

三个方向的处理：
- 方向 1（目录比对）没有走——比"整名不命中再回退"更彻底的接缝前移：执行器把宿主解析后的执行模型直接传给出站组装（`PrepareBodyResolved`），宿主 …[截断]

## #19 [qoder] 流式偶现上游计时事件透传（firstTokenDuration），严格校验的客户端会报错
[closed] 评论 1 条
正文: **环境**：cpa-multi-plugins v0.12.88 + CLIProxyAPI 7.3.17，Windows

qoder 的流式请求偶尔会在 `[DONE]` 前多出来一个奇怪的 chunk：

```
data: {"firstTokenDuration":3037,"totalDuration":3045,"serverDuration":28}
```

没有 choices 也没有 error，客户端没法解析，ZCode 直接报错：

```
Type validation failed: Value: {"firstTokenDuration":1335,"totalDuration":6280,"serverDuration":79}
expected array at choices / expected object at error
```

复现：流式请求 qoder 模型看流的结尾就行。实测 `glm-5.3-flash` 和 `deepseek-v4-pro` 碰到过，`qwen3.8-max`、`kimi-k3` 又是干净的，感觉跟上游路由到 …[截断]
评论@mmqz: 已修复，随 qoder 插件 0.8.25 发出（主程序 tag v0.12.89）。

**根因**：qoder 网关在部分后端路由上会在 `[DONE]` 前往 data 通道发一个裸计时对象（`firstTokenDuration`/`totalDuration`/`serverDuration`），聚合器此前把一切非错误 data 帧都当作补全 chunk 原样透传，严格校验的客户端就死在 …[截断]

## #20 WorkBuddy 国际版请求开始要包含一条system消息
[closed] 评论 1 条
正文: 参考 https://github.com/zqcccc/workbuddy-cliproxy
评论@mmqz: 已核实并修复，随 v0.12.95（workbuddy 0.9.37，commit 0d0bd19）发出。

**问题属实，且比标题更具体**：Global（workbuddy.ai）网关校验的是 `messages[0]`——首条不是 system 就拒（code 11128 "first message is not system prompt"，参考实现 zqcccc/workbuddy-c …[截断]

## #21 ZCode Weekend Build计划无法使用
[closed] 评论 6 条
正文: 请问是无法使用ZCode Weekend Build计划吗（领福利领的）

<img width="381" height="276" alt="Image" src="https://github.com/user-attachments/assets/ff339c27-963b-4678-b449-7f8f941a1423" />

<img width="617" height="411" alt="Image" src="https://github.com/user-attachments/assets/8a3b9f72-f2b8-4e7a-8b70-d76e1227bec7" />
评论@mmqz: Weekend Build 套餐走的是 zcode 官方周末活动权益，和普通付费套餐的额度池不是同一条。

从截图看是账号已领到 Weekend Build 但插件面板没有体现/调用失败？需要补充一点信息才能定位：

1. CPA 版本、插件版本（面板右上或 /v0/management/plugins/zcode/config 能看到）；
2. 领取后 CPA 日志里 zcode 的相关行（尤其 …[截断]
评论@AkimioJR: 1. CPA版本：v8.0.4
2. 日志
```
3 天前（2026-09-27）的 zcode 调用报错都在 data/logs/main.log，共 4 条，全部是 provider=zcode / model=glm-5.3-flash：
时间	行号	错误
14:46:02	main.log:31588	超时：Post "https://api.z.ai/api/coding/paas/v …[截断]

## #22 [qoder] adopt 在宿主 auth 管理器就绪前调用 host.auth.get，每次启动必失败（bad envelope）
[closed] 评论 2 条
正文: ## 现象

每次内核启动，qoder 插件 adopt 阶段必现两行：

```
adopt qoder-cn-<uid>.json: get failed: host.auth.get: bad envelope
adopt qoder-intl-<uid>.json: get failed: host.auth.get: bad envelope
```

凭据本身正常（面板账号 active、模型发现正常），所以表面上是无害噪音；但实际后果是 **adopt 迁移永远不会执行**——真有 `type: qoder-cn/intl` 遗留文件时也不会被迁移。

环境：v0.12.100 / qoder 0.8.28，宿主 CLIProxyAPI 8.0.3，Windows。8 个凭据文件时 100% 复现，v0.12.95 起一直存在。

## 根因

`startAdoption()` 在插件注册后的后台 goroutine 里立即跑 `adoptForeignAuths()`：先 `host.auth.list`（走磁盘扫描，成功），再按 `auth_index` 调 `ho …[截断]
评论@mmqz: 已修复，qoder 0.8.29（release v0.12.101）。

感谢这份分析——根因、证据和修法建议都齐了，直接按报告落地：

1. **重试阶梯**：`startAdoption()` 现在以 10 次 × 2s 重试，直到宿主 auth 管理器就绪（auth_index 可解析）为止——与 bfSan/qoder-cpa-plugin 9d0aaaf0 的做法一致。
2. **物理 …[截断]
评论@mmqz: 对应修复已随 v0.12.101（qoder 插件 0.8.29）发布并回复在上方：重试阶梯 + 物理读兜底 + 日志改进，trae / workbuddy 同款竞态一并镜像修复。先关闭处理；如启动仍复现 bad envelope，欢迎贴新日志重开或另开 issue。

## #23 zcode限时活动套餐自动领取
[closed] 评论 3 条
正文: 这个可以实现吗？
评论@mmqz: 可以做，但目前签到通道只覆盖「每日 campaign 权益领取」（GET /me/campaigns + /{campaignId}/claim，CN/Intl 两个区都有）。

「限时活动套餐」的领取入口是按活动变的：不同活动的 claim 端点、入参、资格校验都不一样，盲发请求很容易撞 403/资格不足。如果你手上有某个具体活动的请求证据（浏览器 F12 → 该活动的领取请求：URL、meth …[截断]
评论@mmqz: 进度更新：这个功能已经落地。v0.12.102（zcode 插件 0.2.0，2026-09-29 发布）内置了**活动自动领取调度器**（参考上游成熟实现移植）：默认每 5 分钟轮询一次 billing/preview，自动挑选当前可领的活动套餐并领取（默认挑优先级最高的，可用 claim_plan_id 锁定指定活动）；退避语义与上游一致——成功后持有到活动结束、窗口未开则等待、失败类错误按表 …[截断]

## #24 login_variant/login_region 设为 intl 但 OAuth 登录仍走 CN（trae / qoder / workbuddy 三个插件一致）
[closed] 评论 2 条
正文: ## 环境

- CLIProxyAPI **v8.0.4** + **cpa-multi-plugins v0.12.100**
- Linux amd64（Debian），CPA 以 `127.0.0.1:8320` 监听
- 插件版本：trae **0.12.66** / qoder **0.8.28** / workbuddy **0.9.44**

## 问题

配置里 `login_variant` / `login_region` 明确设为 `intl`，**但 OAuth 登录启动时全部走 CN**。三个插件（trae / qoder / workbuddy）行为一致。

### 配置（API 回读，非猜测）

```console
$ GET /v0/management/plugins/trae/config
{"enabled":true,"login_variant":"intl"}

$ GET /v0/management/plugins/qoder/config
{"enabled":true,"login_region":"intl"}

$ GET / …[截断]
评论@mmqz: 已修复，trae 0.12.68 / qoder 0.8.29 / workbuddy 0.9.45（release v0.12.101）。

排查结论：管理端保存、GET 回读、config.yaml 三处都是对的，问题出在**插件侧对宿主发来的 config_yaml 的解析**上，两层叠加：

1. **区域重置不是 sticky**。trae 在 v0.12.3 就修过：宿主在 auth- …[截断]
评论@numens: @mmqz 
CPA **v8.0.4**
cpa-multi-plugins **v0.12.103**
workbuddy **0.9.46**   login_platform：CLI   login_region：intl
oauth登录报错：错误:启动插件 OAuth 失败: timeout of 30000ms exceeded

## #25 认证文件配置的代理/权重/优先级/前缀等，在刷新后重置为默认
[closed] 评论 1 条
正文: 目前使用workbuddy和zode，配置了代理和优先级等自定义参数，过一段时间就没了测试了下，麻烦带佬看下，抽空修复下，谢谢！
评论@mmqz: 已修复，workbuddy 0.9.45 / zcode 0.1.9（qoder / trae / mimo 同款问题一并修），release v0.12.101。

根因：插件在刷新 token / 写额度 note / 启停账号时，会用插件自己认识的那几个字段**从零重建**认证文件 JSON——宿主写入文件的运营者字段（proxy_url、weight、priority、prefix、lab …[截断]

## #26 [qoder] 国际版（Intl）账号的签到/活动未适配：面板与自动签到仅覆盖 CN，缺少「登录客户端 300 分」与「每日领取 100 积分」
[closed] 评论 3 条
正文: ## 环境

- CLIProxyAPI **v8.0.4**
- cpa-multi-plugins **v0.12.103**
- qoder 插件 **0.8.30**（`login_region: intl` 已生效，CPA 日志可见 `qoder: login_region=intl applied (new logins target INTL)`）
- 账号：`qoder-intl-01a0f157-…`（**Intl 区**，Free 套餐）

## 问题

**Intl 账号可以正常导入和使用（`qfmodel` 实测可出话），但面板的签到 / 汇总 / 过滤 / 自动签到全部只走 CN 分支，国际版的两个活动没有适配。**

### 1. 面板文案与控件只覆盖 CN

面板顶部副标题：

```
积分余额 · CN 每日签到（09:00/21:00）· 耗尽自动关
```

- 自动签到复选框：**`自动签到(CN)`**
- 过滤标签：**`全部 1` / `CN 1` / `耗尽 1`** —— **没有 `Intl` 标签**
- 汇总行：**`CN 可用 0 …[截断]
评论@mmqz: 感谢这份报告——面板四个 Intl 缺口全部确认属实，已随 **v0.12.104**（qoder 插件 0.8.32）修复：

**1. 面板 Intl 维度补齐**
- 过滤条新增 `Intl` 标签；计数改为按账号卡片的真实区域统计（此前 Intl 账号被无条件计入 CN 计数，所以你看到 `全部 1 / CN 1`）；
- 汇总行按区域拆分：`CN 可用 X / 已用 Y · Intl 可 …[截断]
评论@mmqz: ## v0.8.63（qoder 插件 0.8.60）——intl 每日 100 端到端修复，实弹 +100 到账

按"去上游找签到端点"的思路翻完了全部上游实现（wallechfox/sunp1/chevy222/L0NE-6 四个独立签到脚本 + TraeWorkAssistant + qoder2api-hub）：**所有实现用的端点与插件完全一致**（`GET /sash/api/v1/ …[截断]

## #27 [qoder] 国际版（Intl）客户端协议实录：设备码 OAuth 登录 / 机器身份头来源 / 「每日 100」实为客户端自动领取 / 300 试用资格边界（附脱敏抓包）
[closed] 评论 5 条
正文: ## 环境

- 客户端：Qoder 桌面版 **0.4.3**（win32-x64，Electron 43.1.1 / Chrome 150）
- 抓包：mitmproxy 12.2.3 串在 FlClash 之前（`--mode upstream:http://127.0.0.1:7890`），系统代理指向 mitmproxy，CA 装 LocalMachine\Root
- 样本：一次「登出 → 用另一个账号登录 → 打开 Usage 面板」的完整会话，**256 条 HTTP flow**
- 账号：Intl 区，Google SSO 注册

## 发现 1：登录 = 设备码 OAuth + PKCE（非浏览器直跳）

```
GET  https://openapi.qoder.sh/api/v1/deviceToken/poll?nonce=<uuid>&verifier=<43字符>
     未授权期间反复返回 404（轮询），用户在浏览器授权后返回 200
     ← {"id":"<uuid>","token":"dt-…"(27字符),"refresh_toke …[截断]
评论@mmqz: 感谢这份实录，抓包链路完整、脱敏规范，几个结论直接纠正了我们此前的认知空白，已在 #26 的修复（v0.12.104）中核对/采纳：

**逐条核对结果：**

1. **发现 1（设备码 OAuth + PKCE）**：确认 Intl 客户端唯一登录路径是 `deviceToken/poll`（dt-/drt-）→ `jobToken`（jt-/jrt-）。插件目前的导入路径是 PAT → jo …[截断]
评论@Xyloz3n: ## 补充实测（重要更正）：无客户端也能领到「每日 100」

正文「发现 3」把资格判给了**客户端会话**，我们随后又做了一轮对照，**这条结论需要修正** —— 至少 Intl 区不是这样。另，正文「发现 2」里「不带机器头就 `showCampaign:false`」也**没能稳定复现**（同账号在活动已领取后，只带 `Cosy-ClientType` 同样能看到该活动），一并撤回。

# …[截断]

## #28 Zcode使用出现错误
[closed] 评论 1 条
正文: 插件版本: 0.2.0

```log
[2026-10-03 17:24:58] [--------] [warn ] [openai_auth.go:336] Token refresh attempt 1 failed: token refresh failed with status 401: {
[2026-10-03 17:25:00] [--------] [warn ] [openai_auth.go:336] Token refresh attempt 2 failed: token refresh failed with status 401: {
[2026-10-03 17:25:02] [--------] [warn ] [openai_auth.go:336] Token refresh attempt 3 failed: token refresh failed with status 401: {
[2026-10-03 17:25:02] [--------] [debug] [conductor_refresh.go:642] refreshed  …[截断]
评论@AkimioJR: 解决了，非插件问题

## #29 将不同平台的国际版/cn版的oauth入口拆开
[closed] 评论 2 条
正文: 建议将不同平台的国际版/cn版的oauth入口拆开
以方便登录不同区域的账号
评论@Xyloz3n: 补充一条 trae **intl** 的实测记录（CPA v8.0.8 / trae.so v0.12.69），与 #29「拆开 intl/cn 入口」同源。

## 现象

面板 trae 额度列不出来：`GET /v0/management/plugins/trae/credits` 对 6 个 intl 账号全部返回

```
ent_usage: upstream session_dead …[截断]
评论@mmqz: 两条线都已落地（[v0.8.58](https://github.com/mmqz/cpa-multi-plugins/releases/tag/v0.8.58)）：

## 1. 分渠道包（本 issue 的主体诉求）
从 v0.8.58 起，每个平台除默认统一包外，新增 **`cpa-multi-plugins-split-<os>-<arch>.zip`**（分渠道包），包含 7 个独立的变 …[截断]

## #30 WorkBuddy 国内版本输出问题
[closed] 评论 4 条
正文: 我最近在Pi长任务里使用发现会输出`<thought></thought>`、`<analysis></analysis>`、`<summary></summary>`内容
评论@mmqz: 感谢反馈，这个问题目前缺少可定位的错误样本——`<thought>`/`<analysis>`/`<summary>` 标签可能来自两处：上游模型把思考内容以标签形式混入 `content`（插件侧未剥离），或客户端（Pi）自身的协议解析/渲染问题。复现需要以下信息：

1. **环境信息**：插件版本（对应哪个 release 的 .so）、CPA 内核版本、账号区域（auth 文件里的 `re …[截断]
评论@Misaka09982: > 感谢反馈，这个问题目前缺少可定位的错误样本——`<thought>`/`<analysis>`/`<summary>` 标签可能来自两处：上游模型把思考内容以标签形式混入 `content`（插件侧未剥离），或客户端（Pi）自身的协议解析/渲染问题。复现需要以下信息：
> 
> 1. **环境信息**：插件版本（对应哪个 release 的 .so）、CPA 内核版本、账号区域（auth 文件 …[截断]

## #31 [workbuddy] 腾讯网关将 Codex CLI 默认开篇系统提示词列入 11128 渠道风控黑名单，导致所有会话首轮被拒
[closed] 评论 0 条
正文: ## 环境与版本
- 插件版本：workbuddy 0.9.46 / 0.9.48 (Windows amd64 / Linux)
- CPA 内核版本：CLIProxyAPI v8.0.12+ / v8.0.13
- 客户端：Codex Desktop / Codex CLI
- 涉及模型：`deepseek-v4.1-flash`、`space-bunny` 等全部 WorkBuddy 模型

## 问题现象
在 Codex Desktop 或 Codex CLI 中配置 WorkBuddy 渠道后，发起任何对话（即使只发送简单的“你好”），首轮请求必定在 2~5 秒后报错失败：

```json
HTTP 500 · 上游渠道风控（code 11128）
raw: {
  "code": 11128,
  "msg": "Illegal API invocation from an unapproved channel",
  "requestId": "79b2ef3d-ede3-4372-bc5b-985892980790",
  "displayMsg": {
    "e …[截断]

## #33 trae 提示设备绑定 BOUND  与本凭证不一致
[closed] 评论 2 条
正文: cpa在本地linux上部署，使用日常pc登录，在插件粘贴的回调地址，能看到信息，但是提出错误
设备绑定
BOUND · 9r57v1d5d58prv · 与本凭证不一致

cpa日志，重新把绑定也无效，
uid=xxxxxx: isLogin=true bindStatus="BOUND" bound="9r57v1d5d58prv" local="xxxxxx" — 绑定不一致为 9074 风控高危，建议面板退出重新登录以重绑设备

<img width="1454" height="935" alt="Image" src="https://github.com/user-attachments/assets/c96d75ba-b788-4967-88b3-790cc4c701b0" />
评论@mmqz: **机制已澄清并在 v0.8.65（trae 0.12.74）修复（commit 428a49c）**——你看到的 `BOUND · 9r57v1d5d58prv · 与本凭证不一致` 是 0.12.72+ 的面板风控提示：服务端记录该账号绑定在设备 `9r57v1d5d58prv` 上，而本地凭证携带的设备 id 与之不符（常见于凭据在不同机器/插件间导出导入）。这个判定本身是服务端事实，插件侧 …[截断]
评论@mmqz: **终局根因定案（v0.8.70 / trae 0.12.77，2026-10-12 live 实证）**——本 issue 报告的「设备绑定 BOUND 与本凭证不一致」类问题，今日在同账号上完成了全链路定性：

1. **服务端的 `BoundDeviceID` 是其内部设备号**（本账号实测 `kxrldxj552p5k6`），与客户端 `DeviceInfo.DeviceID` 永不相等— …[截断]

## #34 qoder 在dsh中无法使用。提示developer非法
[closed] 评论 2 条
正文: 提示信息：
{"error":{"message":"qoder upstream error: status=400 code=provider_error type=provider_error: Error in upstream response: developer is not one of ['system', 'assistant', 'user', 'tool', 'function']","type":"server_error","code":"internal_server_error"}}
评论@mmqz: ## 根因与修复（v0.8.64 / qoder 0.8.61）

**根因**：Qoder 网关的消息校验器只接受 `['system', 'assistant', 'user', 'tool', 'function']` 五种角色，而 o1/gpt-5 时代的 OpenAI 客户端（dsh 即此类）会把指令消息以 `role: "developer"` 发出。插件此前按逐字节透传原则原样转发， …[截断]
评论@mmqz: **实弹补充（2026-10-10，intl 账号 u673e7fcc 真凭证）**

- chat 实弹腿结论：机房 IP 下所有形态的请求（含原始 developer 载荷与修复后载荷）都被网关以 `10605 isQueued=true queueType=p3` 收队，**整 3 分钟后**被服务端 h2 INTERNAL_ERROR 重置——角色校验在队列放行之后才发生，机房路径永远到不 …[截断]

## #35 workbuddy-global: 免费模型(0x)每日限额返回 200+空内容，不冷却不失败上报，会话粘性绑死在限额账号
[closed] 评论 3 条
正文: ## 问题

workbuddy 插件的**异步流式路径**在免费模型触发**每日限额**时不报错、不冷却、不上报失败，导致：

1. 客户端看到 `200 + 空 content`（毫秒级返回，正常请求是 5~20 秒）
2. 宿主 CPA 认为请求成功，**不冷却该凭据**，会话粘性继续绑死在限额账号上
3. 用量监控记录 `failed=0`、`input_tokens=0`、`output_tokens=0` —— 完全看不到失败请求
4. 唯一恢复手段是人工去面板禁用该账号

## 故障语义（请重点关注这一条）

- 触发对象是 **0x 模型**（catalog 里 credits 乘数为 `x0.00` 的免费模型，如 `deepseek-v4.1-flash`）
- 触发条件是**每日用量达到上限**（账号级/模型级限额），**不是**积分耗尽（14018）
- 上游返回的是 **HTTP 200 + 流内错误帧**，**不是 429** —— 所以插件 `fallback.go:85` 的 429 分支完全没被触发，`markCooldown` 从未被调用

这与插件 …[截断]
评论@mmqz: 已在 **v0.8.66**（workbuddy 0.9.57，commit 0d50f05）修复并推送，感谢这份异常完整的故障语义分析——「HTTP 200 + 流内错误帧、非 429、非 14018」这个定位直接决定了修复的落点。

**根因确认：**`fallback.go:85` 那个只认 429 的分支是旧版自编译布局；当前代码（v0.9.29 起）的 `workBuddyStreamF …[截断]
评论@mmqz: **v0.8.67 补充分级（workbuddy 0.9.58）**——在 v0.8.66 冷却表之上的一个针对性改进：

60 秒的 unknown 兜底对"每日限额"这个具体形态其实偏短：额度要等到自然日重置才回来，60 秒窗口意味着被限的 (账号, 模型) 对**每分钟空转一次重试**（一天最多 1440 次无效探测）。v0.8.67 给冷却表加了**每日额度分级**：

1. **分类器* …[截断]

## #36 [workbuddy] finish_reason:"stop" returned together with non-empty tool_calls; login_region:intl switches ALL realms (incl. CN) to the broken stream path
[closed] 评论 3 条
正文: Environment: CLIProxyAPI v8.0.23, cpa-multi-plugins v0.8.63, linux/arm64

## Symptom
POST /v1/chat/completions with `tools` returns 200 with message.tool_calls
populated but finish_reason:"stop". Per the OpenAI spec this must be
"tool_calls"; any tool-calling agent loop breaks on the contradiction.

## Control matrix (same host, same binary)
A) clean config (no login_region set), workbuddy CN account:
   model glm-5.3-flash + tools  → finish_reason:"tool_calls" ✅
B) clean config, workbuddy Globa …[截断]
评论@mmqz: 已在 **v0.8.66**（workbuddy 0.9.57，commit 0d50f05）修复并推送。控制矩阵（A/B 正常、C 稳定复现）把范围钉得很准，谢谢。

**根因：** codebuddy.ai（Intl/IDE）网关的 OpenAI 兼容转换把内部 Anthropic 风格的 stop 语义映射成 `finish_reason:"stop"`，**不检查同一响应是否发过 tool …[截断]
评论@mmqz: **v0.8.67 补充修复（workbuddy 0.9.58）——平台血统持久化**，把 issue 里 "scoping the IDE dialect per-credential" 的诉求钉死在登录层：

v0.8.66 修复了终帧矛盾；但排查中发现一个相邻的血统错配：`login_platform: ide`（或 intl 登录）走 IDE 入口铸造的 token，**聊天时却以 CLI …[截断]

## #37 [qoder] image_url content parts are dropped when building the upstream body — image-only messages fail with "no user message in request"
[closed] 评论 3 条
正文: Environment: CLIProxyAPI v8.0.23, cpa-multi-plugins v0.8.63 (qoder 0.8.60),
linux/arm64

## Repro A — image-only message (hard failure)
POST /v1/chat/completions
{"model":"qfmodel","messages":[{"role":"user","content":[
  {"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}]}]}
→ 500 {"error":{"message":"body build: no user message in request"}}
Reproduces on both realms, verified with realm-exclusive models:
- q37fmodel (CN-only catalog)
- ultimate (Intl-only catalog)
Also obser …[截断]
评论@mmqz: 已在 **v0.8.66**（qoder 0.8.63，commit 0d50f05）修复并推送。两个 Repro 的形态差异（硬失败 vs 静默丢失）抓得很准——workbuddy 对照实验证明 payload 形状合法、问题在 qoder 通道本身，这个方法论正是需要的。

**根因确认：** QoderWork 的 `agent_chat_generation` 请求体**没有图像字段**— …[截断]
评论@mmqz: **v0.8.67 证据链补充**——v0.8.66 选择"诚实拒绝"后，我们又从官方客户端逆向出了一组新证据，留档在这里作为后续升级为"转发"的路线图：

**1. 模型层确有视觉能力（实弹目录）**：intl 账号目录 15/15 模型 `is_vl=true`（`auto`/`ultimate`/`performance`/`efficient`/Qwen3.x/Kimi/GLM/DeepS …[截断]

## #38 [trae] OAuth login: callback received but ExchangeToken hangs until TTL expiry; login_status outcome is empty
[closed] 评论 3 条
正文: Environment: CLIProxyAPI v8.0.23, cpa-multi-plugins v0.8.63 (trae 0.12.73),
linux/arm64

## Flow
1. GET /v8/management/oauth/auth-url?provider=trae → returns
   www.trae.cn/authorization?login_channel=native_ide&client_id=ono9krqynydwx5
   &auth_callback_url=http://127.0.0.1:<port>/authorize&code_challenge=...
2. Browser (already logged into trae.cn): authorization confirmed, page
   redirects to the local callback.
3. GET /v0/resource/plugins/trae/login_status reports:
   {"pending":true,"callb …[截断]
评论@mmqz: **根因已定位并修复（v0.8.65 / trae 0.12.74，commit 428a49c）**——你报告的两个症状是两个独立的 bug，都出在 0.12.73（v0.8.62）引入的变更上：

### 1. 登录挂起：回调已收到但 ExchangeToken 永远不完成、无 outcome

**根因**：0.12.23 的 15 秒 grace 自完成**只在 resource 路由路径 …[截断]
评论@mmqz: **v0.8.68 (trae 0.12.75) follow-up — the `ent_usage session_dead` / 401-1001 face, root-caused live on a real cn credential.**

A field report after v0.8.65 still showed `ent_usage: upstream session_d …[截断]

## #39 可否维护registry.json，方便插件商店更新？
[closed] 评论 4 条
正文: 
评论@mmqz: 已维护，v0.8.71 起生效（d8cf297）。

## 本次做了什么

- `registry.json` 各插件 `version` 字段此前自首次提交起一直冻结在 `0.1.0`，现已与各插件 `VERSION` 文件对齐：**workbuddy 0.9.59 / qoder 0.8.63 / trae 0.12.77 / zcode 0.2.1**；
- 补上了缺失的 **mimo**（ …[截断]
评论@mmqz: 已按上一条评论的承诺把商店友好字段全部做完，v0.8.72（bc8b6d1）起生效，本 issue 交付闭环。

## registry.json schema v2

原始地址（商店可直接拉取）：
`https://raw.githubusercontent.com/mmqz/cpa-multi-plugins/main/registry.json`

在原有 id/name/descripti …[截断]

## #40 wb国际版反代500报错
[closed] 评论 2 条
正文: HTTP 500
上游渠道风控（code 11128）——通常由请求特征或频率触发，与账号状态无关；请降低请求频率稍后再试，持续出现请更新插件以对齐官方客户端请求特征。 // Upstream channel risk control (11128); back off and retry — request-shaped, not account-level. | raw: {"code":11128,"msg":"request illegal","requestId":"784d91a6-b358-4b5c-bc4d-5f3cef46a276","displayMsg":{"en":"Request blocked. Please send it again","zh":"请求被拦截，请重新发送","zh-hant":"
已更新最新版本插件仍出现该问题
评论@sciman-top: 根因定位（v0.8.68 / workbuddy 0.9.58）：这不是风控频率问题，是 **INTL realm 漏了 system-first 自动注入**。

`ensureSystemMessageInPlace` / `ensureSystemMessage` 的守卫是 `!isGlobalDomain(sa.Auth.Domain) → return`——只有 Global（workb …[截断]
评论@mmqz: 已定位并修复，v0.8.71 起生效。

## 根因

这不是风控频率问题，而是 **INTL realm 漏了 system-first 自动注入**：

- `ensureSystemMessageInPlace` / `ensureSystemMessage`（payload.go）的守卫是 `!isGlobalDomain → return`——只有 Global（workbuddy.ai …[截断]

## #44 Intl (www.codebuddy.ai) joined the same-day 11128 "Request blocked" wave — conversation-header gate extends to Intl (field evidence, #43 follow-up)
[closed] 评论 1 条
正文: ## Summary

On 2026-10-19 the Intl gateway (`www.codebuddy.ai`) started rejecting chat calls with `11128 "request illegal"` — same day, same error family as #43's Global finding, but with a different `displayMsg`. Extending #43's three conversation-correlation headers to Intl fixes it. #43's assumption that "CN and Intl realms do not check them" no longer holds for Intl.

## displayMsg (full envelope — the log line alone truncates it)

```json
{"code":11128,"msg":"request illegal","displayMsg":{ …[截断]
评论@mmqz: 已修复并发布，**v0.8.73**（[06cf92b](https://github.com/mmqz/cpa-multi-plugins/commit/06cf92b) + [e324b43](https://github.com/mmqz/cpa-multi-plugins/commit/e324b43)，workbuddy 0.9.61）起生效。

## 处理方式

按你的建议折入 #43 …[截断]

## #45 code 11128请求被拦截。
[closed] 评论 1 条
正文: {"error":{"message":"auth_unavailable: no auth available (providers=workbuddy,opencode, model=deepseek-v4.1-flash; last upstream error: 上游渠道风控（code 11128）——通常由请求特征或频率触发，与账号状态无关；请降低请求频率稍后再试，持续出现请更新插件以对齐官方客户端请求特征。 [REDACTED_PATH]: {\"code\":11128,\"msg\":\"request illegal\",\"requestId\":\"5cf2daee-5c06-4702-b2e1-71e2cc48e7f1\",\"displayMsg\":{\"en\":\"Request blocked. Please send it again\",\"zh\":\"请求被拦截，...)","type":"server_error","code":"internal_server_error"}}
使用dsh，国内国际版本均不可用了，昨天晚上还正常使用。
评论@mmqz: 已修复并发布，**v0.8.73**（workbuddy 0.9.61）起生效，请更新插件后重试。

## 根因

上游网关从 2026-10-19 起分波次上线了「官方客户端会话头强校验」，缺失这三个头即判 11128「请求被拦截」：

```
X-Conversation-ID / X-Conversation-Request-ID / X-Conversation-Message-ID
`` …[截断]

## #47 [trae] v0.12.77+ CN login always fails with ExchangeToken 401 code=20403 (Token device not match) — auth-code exchange uses a different device than the authorization URL
[closed] 评论 1 条
正文: ## 摘要

trae **0.12.77+** 的 CN（及 intl）登录在 auth-code `ExchangeToken` 阶段**必然**被上游拒绝：

```
ExchangeToken failed: https://api.trae.cn/trae/api/v3/oauth/ExchangeToken
  => HTTP 401 upstream code=20403 (Token device not match.)
```

根因：v0.12.77 在回调拿到 `userInfo` 后，把登录 ctx 的设备切换成「按 uid 派生的设备」（`applyDerivedIdentityCN/Intl`），
但授权页 URL 里携带的是**安装级 bootstrap 设备**（`ensureLoginDeviceIdentity`）。两者不一致，
而 auth-code `ExchangeToken` 正是设备绑定发生的时刻（`trae_live_rebind_test.go` 已钉死"绑定只在链路签发时选择、此后不可迁移"），
于是每次登录都撞 20403。

在  …[截断]
评论@mmqz: ## 根因确认（与你的分析完全一致）

v0.12.77/v0.12.78 在回调拿到 userInfo 后把登录 ctx 的设备**换装**成 `deriveAccountDeviceIdentity(variant, uid)`，而授权页 URL 带的是 start-login 解析的安装级设备——ExchangeToken 与 URL 设备不一致，上游对每个新签发的 auth code 校验 …[截断]

## #52 magpie ecosystem monitor (daily 06:00 CST)
[open] 评论 6 条
正文: # 🔔 magpie ecosystem monitor

Daily **06:00 Asia/Shanghai** (22:00 UTC) via [`.github/workflows/magpie-monitor.yml`](../blob/main/.github/workflows/magpie-monitor.yml) — also runnable on demand from *Actions → magpie-monitor → Run workflow* (optional `since` input rewinds the cursor for a deep digest).

**Why:** our plugins' protocol layers are byte-aligned with this ecosystem — trae device-bound renewal ← `magpie-community/packages/trae` `SITES["trae-cn"].deviceExchange`; the 9074 root-cause do …[截断]
评论@github-actions[bot]: ## 🚨 magpie monitor digest — 2026-10-23 14:32 CST

**12 protocol-relevant section(s)** since 2026-10-16 14:32 CST.

#### `magpie-community/plugins/packages/trae` → `plugins/trae`
- [`8e479f1`](https:/ …[截断]
评论@github-actions[bot]: ## 🚨 magpie monitor digest — 2026-10-23 14:32 CST

**6 protocol-relevant section(s)** since 2026-10-09 08:00 CST.

#### `magpie-community/plugins/packages/trae` → `plugins/trae`
- [`103bb24`](https:// …[截断]

## #53 zcode新活动查询不到领取
[closed] 评论 1 条
正文: zcode插件版本是2.1

<img width="327" height="413" alt="Image" src="https://github.com/user-attachments/assets/493ae7e2-bb8c-46da-a8fe-c803d4b93383" />

<img width="1098" height="116" alt="Image" src="https://github.com/user-attachments/assets/7fc3927b-4f56-4cd4-ae27-ef1e62cdca02" />
评论@mmqz: ## 情况说明 + 已修复（zcode 0.2.3，v0.8.81）

### 你看到的两件事

**1. 「当前没有可领取的活动」对这个礼包是预期行为**：截图里的 1024 礼包是 **1024 · INVITATION（邀请制/定向）活动**，它由官网通道下发，不经过 `billing/preview` 接口（该接口只列公开可领取 campaign）。你在官网领取成功后（截图一「ZCode  …[截断]

## #55 [workbuddy] 企业版/教育公益版账号额度显示为 0：个人 get-user-resource 返回空 Accounts，应回退到 get-enterprise-user-usage
[closed] 评论 1 条
正文: ## 问题

**企业版 / 教育公益版（教育优惠）WorkBuddy 国内账号在面板上显示 `余0 已用0`，套餐显示 `free`，但账号实际有 2000 企业额度、且能正常出字。**

原因是 `fetchUserResource()` 只走个人计费接口 `/v2/billing/meter/get-user-resource`。企业账号在该接口上返回 **HTTP 200 + 空数据**（`TotalCount: 0`、`Accounts: null`），不是报错，所以插件把它当成「0 积分」展示，而不是「未知」。

账号本身可正常使用：加入池子后 `/v1/chat/completions` 连续请求全部 200，CPA 用量记录也能看到该 `auth_index` 承担请求，上游 `get-enterprise-user-usage` 的 `credit` 随请求单调增长。

## 环境

- CPA 内核：CLIProxyAPI 8.0.40，commit `d946c4fb`，macOS 15.7.9 arm64
- 插件：`mmqz/cpa-multi-plugins …[截断]
评论@mmqz: ## 根因确认 + 已修复（workbuddy 0.9.67，v0.8.81）

这份报告的质量非常高——上游证据（两个接口的完整响应）、生命周期影响分析（`shouldReenableCN` 的死锁）、以及「未知 ≠ 耗尽」的边界讨论都直接命中。全部按建议落地：

### 修复内容

1. **额度回退**（`enterprise.go` 新增）：`enterpriseId` 非空且个人接口 ` …[截断]

## #56 [workbuddy] 企业号需要按账号排除模型（凭证级 excluded_models 会被清空）；顺带请求指纹版本偏旧
[closed] 评论 1 条
正文: ## 一、企业/教育号需要「按账号」排除模型

这是 #55（企业号额度显示 0/0）的后续问题，但影响更实际：**模型权限也是按账号的，而插件只能按渠道排除。**

### 现象

一个 WorkBuddy 教育公益版企业号（2000 额度，`enterpriseId` 非空），动态发现到 54 个模型，但实际权限窄得多。我把它和另外两个国内个人号放在同一个 CN 渠道里，逐个实测 18 个主力模型：

| 能用（10） | 回 `11136 model not allowed`（8） |
|---|---|
| `hy4-preview`、`hy3`、`deepseek-v4.1-flash`、`glm-5.3-flash`、`kimi-k3.1-pro`、`step-5-preview`、`space-bunny`、`minimax-m3`、`minimax-m3.1-flash`、`mimo-v2.6-pro` | `glm-5.3`、`glm-5.2`、`glm-5v-turbo`、`kimi-k3-1`、`kimi-k2.8-preview`、`kimi-k2.7`、`ki …[截断]
评论@mmqz: **已修复 — workbuddy 0.9.69（tag `v0.8.83`）。** 你报告的两部分都处理了，第一部分先交代根因考证，因为它比「加个白名单」深一层。

## 一、凭证级 excluded_models 为什么活不过 12 秒

沿着写入路径逐段考证后的结论：**清空者是插件自己，宿主是无辜的**。

- 宿主的 `host.auth.get` 是 `os.ReadFile` 原样返 …[截断]

## #57 Billing plane carries no machine identity: proposal — per-account derived X-Machine-ID / X-Session-ID + per-request X-Request-ID
[closed] 评论 1 条
正文: ## Observation

`billingHeaders()` sends no device identity at all. Every account's billing and growth calls (billing + growth both ride this header family) present the exact same gateway shape, so a pool of N accounts shows **zero device separation** on the entire non-chat surface.

For contrast, the growth *event body* already carries per-uid derived `machineId`/`sessionId` (growthDeriveID, since 0.9.23) — the billing *headers* have nothing.

## What the official family looks like (per workbud …[截断]
评论@mmqz: **Closing as implemented by #58** (shipped in v0.8.83 / workbuddy 0.9.70).

On your captures question — the honest answer is that our first-hand evidence is thinner than hub's. What we actually have:
 …[截断]

## #59 Proposal to discuss: 429-triggered outbound-identity switch (CLI <-> IDE) before I write any code
[open] 评论 1 条
正文: Opening as a discussion first, deliberately before any implementation — this one changes protocol surface and I'd rather not guess at the design.

## Current behavior

The outbound identity (CLI vs adopted-IDE family) is fixed at login time per credential. On 429/code-6004 the plugin cools the credential×model pair and the host rotates to another auth; the identity itself never changes.

## What workbuddy2api-hub does (reference)

The hub keeps three identity families (desktop / VSCode / CLI) pe …[截断]
评论@mmqz: Design answers, in your numbering:

**1. Upstream observability.** A family switch is observable in principle — same account, same tokens, suddenly speaking the full IDE header family after weeks of C …[截断]

## #61 Design discussion: proactive guardrails (reserve credits / daily caps) before I implement
[open] 评论 1 条
正文: Design-first issue, same as #59 — this one has real config-surface and reset-semantics decisions, so I'd rather align before writing code.

## Current behavior

Guardrails today are passive: lifecycle reconcile disables/deletes a credential once credits are actually exhausted (and model-level 6004 windows cool specific pairs). Nothing stops a credential from being **drained to zero** by routine traffic — daily check-in earnings included.

workbuddy2api-hub ships four proactive knobs (its account …[截断]
评论@mmqz: Design answers, in your numbering:

**1. Subset: `reserve_credits` first, `daily_credits_cap` second, token caps deferred.** Same instinct as yours, for the same reasons. `entry.credits` (the cached ` …[截断]

## #63 [workbuddy] Codex Responses 协议下超大 MCP tools（如 mcp__rea）导致 kimi-k3.1-pro 报错 11133 / 400001 (compactToolDescriptions 格式不匹配)
[open] 评论 0 条
正文: ## 问题现象

在 Codex Desktop（Responses API 协议）环境下使用 WorkBuddy:kimi-k3.1-pro（例如子智能体 spawn_agent 或加载了完整 MCP 扩展的会话）时，请求必挂并返回 upstream 400：

`	ext
[conductor_execution.go:1985] upstream execution failed: provider=workbuddy model=kimi-k3.1-pro auth_file=workbuddy-*.json err=upstream 400: {"code":11133,"msg":"Invalid request parameters","requestId":"...","extError":{"code":"400001","message":"the request parameters were rejected by the model provider",
`

随之触发 cooldown.go 的 60s 熔断保护（modelCooldownUnknown = …[截断]


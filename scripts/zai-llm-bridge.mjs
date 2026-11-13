#!/usr/bin/env node
/**
 * zai-llm-bridge.mjs —— #113 真实 LLM 通路桥（环境件，与 rust-env.sh 同类）。
 *
 * 作用：把本沙箱的 z-ai CLI（glm-4-plus，OpenAI 兼容出参）暴露为本机
 * OpenAI 兼容 HTTP 端点，供 bid-mcp RealGenerator（ureq HTTP 面）调用：
 *   POST /v1/chat/completions  →  z-ai chat --prompt … --system … --output …
 *   响应体 = z-ai 原样 OpenAI JSON（choices/usage 透传）。
 *
 * 纪律（与仓库凭据纪律一致）：
 *   - 不记录/不回显 prompt 与正文（日志只记 时长/状态/字节数）；
 *   - 仅监听 127.0.0.1（无外部暴露面）；
 *   - api_key 只做占位校验（桥自身不做真实认证——本机环回信任边界）。
 *
 * 用法：node scripts/zai-llm-bridge.mjs [port]     # 缺省 8787
 */
import http from "node:http";
import { execFile } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const PORT = Number(process.argv[2] || 8787);
const ZAI_TIMEOUT_MS = 280_000; // 单调用上限（RealGenerator 侧 timeout_secs 须小于此值）

function log(...a) {
  console.log(`[zai-bridge ${new Date().toISOString()}]`, ...a);
}

const server = http.createServer((req, res) => {
  if (req.method !== "POST" || !/\/(v1\/)?chat\/completions$/.test(req.url)) {
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: { message: `not found: ${req.method} ${req.url}` } }));
    return;
  }
  let body = "";
  req.on("data", (c) => {
    body += c;
    if (body.length > 8 * 1024 * 1024) req.destroy();
  });
  req.on("end", () => {
    let messages = [];
    let model = "unknown";
    try {
      const j = JSON.parse(body);
      messages = Array.isArray(j.messages) ? j.messages : [];
      model = j.model || model;
    } catch (e) {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { message: "bad json body" } }));
      return;
    }
    const system = messages
      .filter((m) => m && m.role === "system")
      .map((m) => String(m.content || ""))
      .join("\n\n");
    const user = messages
      .filter((m) => m && m.role !== "system")
      .map((m) => String(m.content || ""))
      .join("\n\n");
    if (!user.trim()) {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { message: "no user content" } }));
      return;
    }
    const t0 = Date.now();
    const runOnce = (attempt) => {
      const outFile = path.join(os.tmpdir(), `zai-bridge-${process.pid}-${Date.now()}.json`);
      const args = ["chat", "--prompt", user, "--output", outFile];
      if (system.trim()) args.push("--system", system);
      execFile(
        "z-ai",
        args,
        { timeout: ZAI_TIMEOUT_MS, maxBuffer: 128 * 1024 * 1024 },
        (err) => {
          const ms = Date.now() - t0;
          try {
            if (err) throw err;
            const data = JSON.parse(fs.readFileSync(outFile, "utf-8"));
            fs.unlink(outFile, () => {});
            const contentLen = String(
              (data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) || "",
            ).length;
            log(`ok model=${model} ${ms}ms out=${contentLen}ch${attempt ? ` (retry#${attempt})` : ""}`);
            res.writeHead(200, { "Content-Type": "application/json" });
            res.end(JSON.stringify(data));
          } catch (e) {
            try { fs.unlink(outFile, () => {}); } catch {}
            const msg = String(e);
            const is429 = msg.includes("429") || msg.includes("Too many requests");
            // 429 限流：长退避（45s/90s/150s——实测恢复窗口 ~5 分钟）；
            // 其它瞬时故障：短退避（3s/8s）。最多 3 次。
            if (attempt < 3) {
              const backoff = is429 ? [45_000, 90_000, 150_000][attempt]
                                    : [3_000, 8_000, 15_000][attempt];
              log(`retry#${attempt + 1}${is429 ? "(429)" : ""} model=${model} ${ms}ms err=${msg.slice(0, 120)} → ${Math.round(backoff / 1000)}s 后重试`);
              setTimeout(() => runOnce(attempt + 1), backoff);
              return;
            }
            log(`fail model=${model} ${ms}ms err=${msg.slice(0, 200)}`);
            res.writeHead(502, { "Content-Type": "application/json" });
            res.end(
              JSON.stringify({
                error: { message: `z-ai bridge failure: ${msg.slice(0, 400)}` },
              }),
            );
          }
        },
      );
    };
    runOnce(0);
  });
});

server.listen(PORT, "127.0.0.1", () => {
  log(`listening on http://127.0.0.1:${PORT}/v1/chat/completions`);
});

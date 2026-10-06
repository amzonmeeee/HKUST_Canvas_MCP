# HKUST Canvas MCP

專為 UST BB 體質設計嘅 Canvas MCP。

功課 deadline、lecture notes、announcements，唔使每次都喺 Canvas 入面逐頁撳。喺 terminal 或支援 MCP 嘅 AI agent 入面，就可以查課程、睇功課要求、搵教材同跟進待辦事項。

由 [amzonmeeee](https://github.com/amzonmeeee) 獨立維護，專注香港科技大學（HKUST）嘅 [Canvas](https://canvas.ust.hk) 使用體驗。沿用原專案嘅 **Chrome session 認證**：先喺 Chrome 登入 Canvas，再由本機工具讀取現有 session。

- `canvas-mcp` — 將 Canvas 工具提供畀 MCP clients。
- `canvas` — 喺 terminal 使用同一套工具。
- 課程、功課、成績、公告、討論區、pages、modules 同檔案查詢。
- 功課提交支援先 preview、再 confirm；macOS 另有本機排程提交。

Agent skill：[`skills/canvas-cli/SKILL.md`](skills/canvas-cli/SKILL.md)。完整指令表：[`docs/cli.md`](docs/cli.md)。

## 安裝

需要 Python 3.11 或以上，以及 `uv`。

```bash
uv tool install git+https://github.com/amzonmeeee/HKUST_Canvas_MCP.git
canvas --help
```

要固定版本，可以喺 repo URL 後加 `@main` 或 `@<tag-or-commit>`。

## 連接 HKUST Canvas

先用 Chrome 開啟 [canvas.ust.hk](https://canvas.ust.hk)，完成 HKUST 登入，確認已經入到 Canvas。

目前透過 `CANVAS_BASE_URL` 指定 HKUST 站點。喺執行 CLI 嘅 terminal 設定：

```bash
export CANVAS_BASE_URL=https://canvas.ust.hk
canvas auth-status
canvas courses --all --limit 5
```

macOS 如出現 Keychain 存取提示，允許後先可以讀取 Chrome cookies。Session 過期時，返 Chrome 重新登入 Canvas，再試一次。

如果有多個 Chrome profiles，可以查看並選擇已登入 HKUST Canvas 嗰個：

```bash
canvas settings profiles
canvas settings choose-profile
```

非互動環境要直接提供 profile 名稱：`canvas settings choose-profile "你的 Chrome profile 名稱"`。亦可以用 `CANVAS_CHROME_PROFILE` 或 `CANVAS_CHROME_PROFILE_PATH` 指定。

## MCP 設定

將以下設定加到你使用嘅 MCP client。`env` 會確保 MCP server 使用 HKUST Canvas，即使 client 唔係由 terminal 啟動。

```json
{
  "mcpServers": {
    "hkust-canvas": {
      "command": "canvas-mcp",
      "args": ["--transport", "stdio"],
      "env": {
        "CANVAS_BASE_URL": "https://canvas.ust.hk"
      }
    }
  }
}
```

如需指定 Chrome profile，可喺同一個 `env` 加入 `CANVAS_CHROME_PROFILE`，值填實際 profile 名稱。

亦可以手動啟動；以下指令沿用上面設定嘅 `CANVAS_BASE_URL`：

```bash
canvas-mcp --transport stdio
canvas-mcp --transport http --host 127.0.0.1 --port 8000
```

## CLI 用法

先搵返自己嘅課程：

```bash
canvas courses --all
canvas resolve "COMP1021" --all
canvas todo
```

以下 `12345` 同 `67890` 分別係示例 course ID 同 assignment ID，請換成你課程嘅實際 ID：

```bash
canvas course context 12345
canvas assignments list 12345 --bucket upcoming
canvas assignments show 12345 67890 --include-submission
canvas files list 12345
canvas url "https://canvas.ust.hk/courses/12345/assignments/67890"
```

各指令嘅 flags 以 `canvas --help` 同子指令嘅 `--help` 為準。想直接呼叫底層工具，可以用 `canvas tool list` 同 `canvas tool run <name> --args '{...}'`。

## 輸出格式

Terminal 預設顯示易讀格式；redirect 或 pipe 輸出時預設使用 compact JSON。全域 `--output` 選項要放喺子指令前面：

```bash
canvas --output pretty assignments submissions scheduled
canvas --output json courses
export CANVAS_OUTPUT=json
```

`--output auto|pretty|json` 優先於 `CANVAS_OUTPUT`。`tool` 指令同內部排程執行預設使用 JSON，即使喺 terminal 執行亦一樣。JSON 保留完整回應；pretty 格式會省略部分常規 metadata，並標示省略情況。

JSON 模式嘅操作錯誤會以結構化資料輸出到 stdout；pretty 模式則喺 stderr 顯示。Preview 被拒絕時 exit code 為 1，工具參數無效時為 2。`auth-status` 同 settings 查詢會回報狀態；框架嘅 help 同選項解析錯誤保留 Typer 原本嘅文字格式。JSON 模式選擇 profile 時需要明確提供名稱，唔會彈出互動提示。

## 本機開發

```bash
git clone https://github.com/amzonmeeee/HKUST_Canvas_MCP.git
cd HKUST_Canvas_MCP
uv sync
uv run canvas --help
```

## 原專案與致謝

本專案以 [ynbh/canvasmcp](https://github.com/ynbh/canvasmcp) 為基礎發展，現由 amzonmeeee 獨立維護，方向集中喺 HKUST Canvas。

感謝原作者提供 Canvas CLI、MCP 工具、Chrome session 認證同測試基礎。原專案採用 MIT License；本專案保留原作者嘅版權聲明，詳見 [LICENSE](LICENSE)。

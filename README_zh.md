# WebTransport OSC Hub

基于 WebTransport（HTTP/3）的 SuperCollider 低延迟双向 OSC 中继系统。

## 特性

- **混合基础架构**: 以支持 WebTransport 的浏览器作为中继客户端，通过 Node.js 桥接连接各参与者的 SuperCollider 环境。
- **Python CLI 桥接**: `local.py` 以单个 Python 脚本实现与 bridge.js + 浏览器相同的连接——无需浏览器。
- **混合传输**: 演奏数据自动使用数据报（低延迟），SynthDef·Buffer 传输使用流（注重可靠性）。
- **会话隔离**: 通过会话 ID 可同时运行多个独立会话。
- **加入/退出通知**: 当参与者进入或退出会话时，Hub 广播 `/hub/join <name>` 和 `/hub/leave <name>`。
- **无改写模式**: `--no-rewrite` 标志使 OSC 帧不经地址改写直接传递。

## 系统架构

| 组件 | 说明 |
|------|------|
| **Hub 服务器**（`wt_oschub.py`） | 在客户端之间中继 OSC 的 Python 服务器（aioquic） |
| **Python 桥接**（`local.py`） | 无需浏览器即可将 SC 直接连接到 Hub 的 Python CLI 桥接 |
| **Web 客户端**（`index.html`） | 连接到 Hub 的基于浏览器的客户端 |
| **本地桥接**（`bridge.js`） | 连接 SuperCollider（UDP）与 Web 客户端（WebSocket）的 Node.js 桥接 |

## 演示

公开演示 Hub 可在 `connect.oschub.asia`（端口 `8443`）访问。请注意，该服务器可能并非始终可用。

- **Web 客户端**：在支持 WebTransport 的浏览器中打开 [https://connect.oschub.asia/](https://connect.oschub.asia/)
- **Python CLI 桥接**：`python local.py connect.oschub.asia --session your-session`

## 前提条件

### Hub 运营者
- Python 3.10+
- 拥有固定 IP 或域名的公开服务器
- 有效的 TLS 证书（例如：Let's Encrypt）

### 参与者
- SuperCollider（使用 scsynth 作为音频引擎的环境）
- **选项 A — Python CLI 桥接**（`local.py`）：Python 3.10+ 及 `pip install aioquic`
- **选项 B — 浏览器 + Node.js 桥接**：Node.js（用于运行 `bridge.js`）及支持 WebTransport 的浏览器：Chrome 97+、Edge 98+、Firefox 115+、Opera 83+（Safari 暂不支持）

## 仓库结构

```
.
├── server/
│   └── wt_oschub.py       # Hub 中继服务器
├── bridge-local/
│   └── bridge.js          # 本地 UDP-WebSocket 桥接（选项 B）
├── client-web/
│   └── index.html         # Web 客户端（选项 B）
├── local.py               # Python CLI 桥接（选项 A — 无需浏览器）
├── .gitignore
├── LICENSE                # GNU GPL v3
└── README.md
```

## 安装与运行

### A. Hub 运营者

在公开服务器上部署 `wt_oschub.py`：

```bash
cd server
pip install aioquic
python wt_oschub.py --cert /path/to/fullchain.pem --key /path/to/privkey.pem
```

附加选项（均为可选）：

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--port` | 8443 | Hub 监听端口 |
| `--no-rewrite` | — | 禁用 OSC 地址改写（直接传递帧） |
| `--max-msg-size` | 65536 | 每条消息的最大字节数 |
| `--rate-limit` | 200 | 每个客户端每秒最大消息数 |
| `--log-level` | INFO | 日志级别：`DEBUG`、`INFO`、`WARNING`、`ERROR` |

然后在支持 HTTPS 的 Web 服务器上托管 `index.html`。

> **注意：** Hub 端口默认为 `8443`，可通过 `--port` 修改。Web 客户端新增了 **Hub Port** 输入字段（默认值：`8443`），如果更改了 `--port`，请在该字段中相应调整。无需直接编辑 `index.html`。Hub 服务器的主机名从 `window.location.hostname` 自动获取，因此当 Web 服务器与 Hub 服务器在同一台机器上运行时，无需手动输入 URL。若在不同机器上运行，请直接编辑 `index.html` 中的 `baseUrl`。

在 Linux 服务器上，可以使用 systemd 将 `wt_oschub.py` 作为服务管理，并每天自动重启。请创建以下两个文件：

`/etc/systemd/system/wt-oschub.service`：
```ini
[Unit]
Description=WebTransport OSC Hub
After=network.target

[Service]
WorkingDirectory=/path/to/server
ExecStart=/usr/bin/python3 /path/to/wt_oschub.py --cert /path/to/fullchain.pem --key /path/to/privkey.pem
Restart=on-failure
User=nobody

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/wt-oschub.timer`：
```ini
[Unit]
Description=Daily restart of WebTransport OSC Hub

[Timer]
OnCalendar=*-*-* 04:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

启用并启动两个文件：
```bash
systemctl daemon-reload
systemctl enable --now wt-oschub.service
systemctl enable --now wt-oschub.timer
```

> **注意：** 请根据实际环境调整 `OnCalendar` 的时间和 Python 路径（`which python3`）。

### B. 会话管理者

将 Web 客户端的 URL 和唯一的会话 ID 分享给所有参与者。

### C. 参与者

#### 1. SuperCollider 设置

如果尚未安装，请从 [supercollider.github.io](https://supercollider.github.io) 下载并安装，然后启动 SuperCollider 并启动服务器。

从 Hub 中继的消息会将 OSC 地址改写为 `/remote/<发送者名>/<原始地址>`（例如：`/remote/alice/s_new`）后送达。这样接收方可以识别是谁发送的，并通过 `OSCdef` 进行明确处理。

最简单的设置是通过单个 `OSCdef` 接收所有远程消息，提取原始地址后转发给 scsynth：

```supercollider
// 接收来自 Hub 的所有远程 OSC 消息。
// 地址格式为 /remote/<发送者名>/<原始地址>。
// 会话期间可用 OSCFunc.trace 查看接收到的消息。
OSCdef(\remoteAll, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    // parts = ['remote', 'alice', 's_new', ...]
    var cmd = ("/" ++ parts[2..].join("/")).asSymbol;
    s.sendMsg(cmd, *msg[1..]);
}, nil);
```

只处理特定发送者或命令时：

```supercollider
// 处理来自任意远程参与者的 /s_new
OSCdef(\remoteSNew, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    var senderName = parts[1];
    (senderName ++ " triggered /s_new").postln;
    s.sendMsg(\s_new, *msg[1..]);
}, nil);
```

> **注意：** OSC Bundle 完全支持。Hub 会递归解析包含嵌套的 Bundle，将其中每条消息的地址改写为 `/remote/<发送者名>/<原始地址>`，同时保留 timetag。如果发送方使用了 `sendBundle(delta, ...)`，接收方的 sclang 会解包 Bundle 并将 timetag 作为 OSCdef 处理器的 `time` 参数传递。要保持预期时序并以 Bundle 形式转发给 scsynth，请按如下方式使用 `time`：
> ```supercollider
> OSCdef(\remoteAll, {|msg, time|
>     var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
>     var cmd = ("/" ++ parts[2..].join("/")).asSymbol;
>     var delta = time - thisThread.seconds;
>     if(delta > 0, {
>         s.sendBundle(delta, [cmd] ++ msg[1..]);
>     }, {
>         s.sendMsg(cmd, *msg[1..]);
>     });
> }, nil);
> ```
> 各参与者的内部时钟（`thisThread.seconds`）是独立的，因此难免存在一定误差。使用足够大的 delta（例如 5 秒）可以吸收网络延迟和时钟差异。

**Hub 系统通知：** Hub 会将以下两条 OSC 消息不经地址改写直接发送给所有参与者：

- `/hub/join <name>` — 新参与者加入会话时发送
- `/hub/leave <name>` — 参与者离开会话时发送

```supercollider
OSCdef(\hubJoin,  { |msg| ("→ " ++ msg[1] ++ " 加入").postln }, '/hub/join');
OSCdef(\hubLeave, { |msg| ("← " ++ msg[1] ++ " 离开").postln  }, '/hub/leave');
```

也可以使用其他兼容 SC 的环境。Python（Supriya）和 Clojure（Overtone）的等效设置代码：

**Python (Supriya):**

```python
import threading
from pythonosc import dispatcher, osc_server
from pythonosc.udp_client import SimpleUDPClient

# 发送目标：本地 Node.js 桥接
bridge = SimpleUDPClient("127.0.0.1", 57121)

# 接收 /remote/* 消息并将原始命令中继给 scsynth
def relay(address, *args):
    parts = address.lstrip("/").split("/")
    # parts = ['remote', 'alice', 's_new', ...]
    if len(parts) >= 3 and parts[0] == "remote":
        cmd = "/" + "/".join(parts[2:])
        bridge.send_message(cmd, list(args))

disp = dispatcher.Dispatcher()
disp.map("/remote/*", relay)

receiver = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 57120), disp)
threading.Thread(target=receiver.serve_forever, daemon=True).start()
```

**Clojure (Overtone):**

```clojure
(ns my-session
  (:use overtone.live
        overtone.osc
        overtone.sc.machinery.synthdef))

;; 发送目标：本地 Node.js 桥接
(def bridge (osc-client "127.0.0.1" 57121))

;; 接收 /remote/* 消息并将原始命令中继给 scsynth
(def receiver (osc-server 57120))
(osc-handle receiver "/remote/*"
  (fn [msg]
    (let [parts (clojure.string/split (:path msg) #"/")
          cmd (str "/" (clojure.string/join "/" (drop 3 parts)))]
      (apply snd cmd (:args msg)))))
```

#### 2. 本地桥接设置

```bash
cd bridge-local
npm install ws
node bridge.js
```

选项（均为可选，显示默认值）：

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--sc-port` | 57120 | SC/sclang 接收 OSC 的端口 |
| `--osc-port` | 57121 | 桥接接收来自 SC 的 OSC 的本地 UDP 端口 |
| `--ws-port` | 8080 | 桥接向浏览器公开的 WebSocket 端口 |

#### 替代方案：Python CLI 桥接（local.py）

`local.py` 以单个 Python 脚本同时替代 bridge.js 和 index.html。无需浏览器或 Node.js。

```bash
pip install aioquic
python local.py your-hub-server.com --session my-session
```

选项：

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `server` | （必须） | Hub 服务器主机名 |
| `--port` | 8443 | Hub 服务器端口 |
| `--sc-port` | 57120 | SC 接收端口 |
| `--osc-port` | 57121 | 本地 OSC 接收端口 |
| `--session` | （提示输入） | 要加入的会话 ID |
| `--name` | （可选） | 显示名称 |
| `--insecure` | — | 禁用 TLS 证书验证（用于自签名证书） |

连接完成后，控制台将显示分配的名称和 ID。OSC 路由（数据报或流）遵循与浏览器客户端相同的规则。如果连接断开，桥接将以指数退避（1 秒~30 秒）自动重连。

> **注意：** 使用 `local.py` 时，请将 OSC 发送到端口 57121（`--osc-port`）而非通过浏览器。在 SC 中设置 `~bridge = NetAddr("127.0.0.1", 57121)`（与 bridge.js 用法相同）。

#### 3. Web 连接

在支持 WebTransport 的浏览器中打开 Web 客户端 URL，输入会话 ID、显示名称（可选，不得包含 `/`）、Hub Port（默认值：`8443`，请与 `--port` 保持一致）、Bridge Port（默认值：`8080`，请与 `--ws-port` 保持一致），然后点击 **Connect All**。连接完成后会显示客户端 ID 和显示名称。断线时会以指数退避（1 秒~30 秒）自动重连。

#### 4. 发送 OSC 消息

所有参与者连接后，发送到 `~bridge` 的 OSC 消息将中继给所有参与者的 scsynth。sclang 的基本使用示例：

> **注意：** 节点 ID 在会话内所有参与者之间共享。多个参与者使用相同 ID（例如 `11000`）时会发生冲突，一方的 `/n_set` 或 `/n_free` 可能影响另一方的节点。请考虑按参与者划分 ID 范围（例如从客户端 ID 推导），用 Group（`/g_new`）隔离各参与者的节点，或由单一发送者管理所有节点 ID。

```supercollider
// 发送目标：本地 Node.js 桥接
~bridge = NetAddr("127.0.0.1", 57121);

// 定义并发送 SynthDef
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

~bridge.sendMsg(\d_recv, ~def.asBytes);

// 所有参与者加载 SynthDef 后播放声音
~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);

// 修改参数
~bridge.sendMsg(\n_set, 11000, \freq, 648);

// 释放节点
~bridge.sendMsg(\n_free, 11000);
```

Python（Supriya）和 Clojure（Overtone）的等效发送代码：

**Python (Supriya):**

```python
# 定义 SynthDef 并编译为字节数组
@synthdef()
def sine_synth(freq=440, amp=0.2):
    sig = SinOsc.ar(frequency=freq) * amp
    Out.ar(bus=0, source=Pan2.ar(sig))

bridge.send_message("/d_recv", [sine_synth.compile()])

# 所有参与者加载 SynthDef 后播放声音
bridge.send_message("/s_new", ["sine-synth", 11000, 0, 1, "freq", 432])

# 修改参数
bridge.send_message("/n_set", [11000, "freq", 648])

# 释放节点
bridge.send_message("/n_free", [11000])
```

**Clojure (Overtone):**

```clojure
;; 定义 SynthDef
(defsynth sine-synth [freq 440 amp 0.2]
  (out 0 (pan2 (* amp (sin-osc freq)))))

(osc-send bridge "/d_recv" (synthdef-bytes (:sdef sine-synth)))

;; 所有参与者加载 SynthDef 后播放声音
(osc-send bridge "/s_new" "sine-synth" 11000 0 1 "freq" 432)

;; 修改参数
(osc-send bridge "/n_set" 11000 "freq" 648)

;; 释放节点
(osc-send bridge "/n_free" 11000)
```

> **注意：** `synthdef-bytes` 是 `overtone.sc.machinery.synthdef` 提供的函数，用于将 SynthDef 序列化为 scsynth 所需的二进制格式。

## 技术补充

### 流量路由

满足以下条件的消息将通过 **WebTransport 流** 发送：
- **OSC Bundle**（为保证 timetag 可靠性，始终通过流发送）
- OSC 地址以 `/d_`（SynthDef）、`/b_`（Buffer）、`/sy`（Sync — 用于同步异步命令）开头
- 数据大小超过 1000 字节

其余情况优先使用 **数据报** 以最小化延迟。

### 异步命令同步

scsynth 的许多命令是异步处理的（通过 `/d_recv` 加载 SynthDef、通过 `/b_alloc` 分配缓冲区、通过 `/b_gen` 生成缓冲区等）。发送方简单使用 `/sync` 只能确认**发送方自身的 scsynth** 队列已完成，无法保证远程参与者准备就绪。

`/sync` 可统一应用于任意异步命令组合。例如，要等所有参与者完成 SynthDef 加载和缓冲区填充后再开始播放：

```supercollider
~bridge.sendMsg(\d_recv, ~def.asBytes);       // 异步：加载 SynthDef
~bridge.sendMsg(\b_alloc, 0, 1024, 1);        // 异步：分配缓冲区（1024 帧）
~bridge.sendMsg(\b_gen, 0, \sine1, 0, 1.0/1, 1.0/2, 1.0/3, 1.0/4, 1.0/5, 1.0/6);  // 异步：填充加法合成正弦波
~bridge.sendMsg(\sync, 5678);                 // 等待以上所有操作完成
```

结合 `/who` 和客户端 ID 可实现更可靠的同步。流程如下：

1. 每位参与者在会话开始前执行以下设置代码。收到 `/sync` 时转发给自己的 scsynth，scsynth 确认队列完成后通过 Hub 广播 `/synced`。由于 `OSCdef` 的端口过滤不能可靠工作，这里使用 `thisProcess.addOSCRecvFunc`。
2. 发送者通过 `/who` 获取参与者数量，然后发送异步命令和 `/sync`。
3. 发送者统计收到的 `/synced` 回复，收齐所有参与者的回复后继续。

**参与者设置（会话开始前执行，sclang）：**

```supercollider
// 收到来自 Hub 的 /remote/*/sync 时转发给本地 scsynth，
// 队列完成后通过 Hub 广播 /synced。
OSCdef(\forwardSync, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    if((parts.size >= 3) && (parts[2] == 'sync'), {
        var syncId = msg[1];
        OSCdef(\waitAndReply, {|msg2|
            // scsynth 回复：['/done', '/sync', syncId]
            if((msg2[1] == '/sync') && (msg2[2] == syncId), {
                ~bridge.sendMsg('/synced', syncId);  // 通过 Hub 广播
                OSCdef(\waitAndReply).free;
            });
        }, '/done');
        s.sendMsg('/sync', syncId);  // 转发给本地 scsynth
    });
}, nil);
```

**发送者工作流（sclang）：**

```supercollider
~bridge = NetAddr("127.0.0.1", 57121);
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

// Step 1：获取参与者数量
OSCdef(\whoReply, {|msg|
    var count = msg.size - 1;  // msg[0] 是 '/who/reply'，其余为参与者名称
    var received = 0;

    // Step 3：统计来自所有参与者的 /synced
    OSCdef(\collectSynced, {|msg2|
        received = received + 1;
        if(received >= count, {
            ~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);
            OSCdef(\collectSynced).free;
        });
    }, '/synced');

    // Step 2：发送异步命令和 /sync
    ~bridge.sendMsg(\d_recv, ~def.asBytes);
    ~bridge.sendMsg(\sync, 1234);

    OSCdef(\whoReply).free;
}, '/who/reply');

~bridge.sendMsg('/who');
```

> **注意：** 参与者的 `/synced` 回复通过 Hub 广播，由发送者的 `OSCdef(\collectSynced)` 在端口 57120 接收。发送者自身的 `/synced`（通过 `\forwardSync` 从本地 scsynth 到达）也包含在计数中，因此如果发送者也运行了 `\forwardSync`，`count` 中包含发送者自身。

### 节点管理与 FAILURE IN SERVER 消息

当远程参与者发送 `/s_new` 或 `/n_free` 等 OSC 命令时，sclang 的 Post Window 中可能出现如下消息：

```
FAILURE IN SERVER /n_free Node 11000 not found
FAILURE IN SERVER /s_new duplicate node ID
```

这是因为 sclang 维护着自己的内部节点管理表，该表通过 scsynth 向发出命令的客户端返回的反馈消息（`/n_end` 等）进行更新。当远程参与者通过 Hub 发来命令时，scsynth 的反馈不会通过 Hub 返回给各参与者的 sclang，导致 sclang 的表与 scsynth 的实际状态不一致。

**重要的是，仅凭这些消息无法判断 scsynth 是否正确处理了命令。** `FAILURE IN SERVER` 既可能表示 scsynth 中的实际错误（例如两个参与者使用了相同 ID 导致节点 ID 重复），也可能仅是 sclang 的表与 scsynth 实际状态未同步。仅从消息文本无法区分两者。

要直接查看 scsynth 的实际状态：

```supercollider
s.queryAllNodes;
```

### 缓冲区使用与样本共享

波表或短的生成缓冲区（例如通过 `/b_gen` 进行加法合成）只需通过 Hub 发送 `/b_alloc` 和 `/b_gen` 即可在各参与者的 scsynth 上运行。仅包含参数数据，各 scsynth 会迅速完成。

对于录制好的音频样本，不建议通过 Hub 传输实际音频数据。音频文件通常体积较大，通过 WebTransport 发送会产生较大延迟并给连接带来负担。建议在会话前通过文件共享等方式将样本分发给所有参与者，各自在本地使用 `/b_allocRead` 加载：

```supercollider
// 各参与者在本地加载样本 — 不经过 Hub
s.sendMsg(\b_allocRead, 0, "/path/to/shared-sample.wav");
```

可以使用 `/sync` 确认所有参与者在播放前已完成加载。

### TLS 证书

WebTransport 需要有效的 TLS 证书。公开服务器推荐使用 [Let's Encrypt](https://letsencrypt.org)。**Cloudflare Origin CA 证书目前与 WebTransport 不兼容**，会导致连接错误。本地开发时请使用以下选项启动 Chrome：

```
--origin-to-force-quic-on=yourdomain.com:8443
```

### 防火墙 / 端口要求

Hub 服务器需开放以下端口：

| 端口 | 协议 | 用途 |
|------|------|------|
| 8443（或自定义） | **UDP** | WebTransport（QUIC/HTTP3）— Hub 主端口，可通过 `--port` 修改。 |
| 80 | TCP | Let's Encrypt HTTP-01 验证（证书申请·续期）。使用 DNS-01 验证或已有证书时不需要。 |
| 443 | TCP | 托管 `index.html` 的 HTTPS。在其他服务器上托管时不需要。 |

> **注意：** WebTransport 运行在 QUIC 之上，因此使用的协议是 **UDP 而非 TCP**。请确保 Hub 端口允许 UDP 流量。这一点容易被忽略，请务必注意。

## 许可证

本项目基于 GNU GPL v3 发布。详情请参阅 [LICENSE](LICENSE) 文件。

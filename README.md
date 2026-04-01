# WebTransport OSC Hub

A low-latency, bidirectional OSC relay system for SuperCollider using WebTransport (HTTP/3).

## Features

- **Hybrid Infrastructure**: Relays data via a WebTransport-capable browser, using a Node.js bridge to integrate each participant's SuperCollider environment.
- **Python CLI Bridge**: `local.py` provides the same connection as bridge.js + browser in a single Python script — no browser required.
- **Hybrid Transport**: Automatically switches between Datagrams (for high-speed performance data) and Streams (for reliable SynthDef/Buffer transfers).
- **Session Isolation**: Supports multiple independent sessions using Session IDs.
- **Join/Leave Notifications**: Hub broadcasts `/hub/join <name>` and `/hub/leave <name>` when participants enter or exit a session.
- **No-Rewrite Mode**: `--no-rewrite` flag passes OSC frames verbatim without address rewriting.

## System Architecture

| Component | Description |
|-----------|-------------|
| **Hub Server** (`wt_oschub.py`) | A Python server (aioquic) that relays OSC between clients |
| **Python Bridge** (`local.py`) | A Python CLI bridge — connects SC directly to the Hub (no browser needed) |
| **Web Client** (`index.html`) | A browser-based transport that connects to the Hub |
| **Local Bridge** (`bridge.js`) | A Node.js bridge connecting SuperCollider (UDP) and the Web Client (WebSocket) |

## Prerequisites

### For Hub Operators
- Python 3.10+
- Public server with a fixed IP/Domain
- Valid TLS certificate (e.g., Let's Encrypt)

### For Participants
- SuperCollider (any environment using scsynth as the audio engine)
- **Option A — Python CLI Bridge** (`local.py`): Python 3.10+ and `pip install aioquic`
- **Option B — Browser + Node.js Bridge**: Node.js (for `bridge.js`) and a WebTransport-capable browser: Chrome 97+, Edge 98+, Firefox 115+, Opera 83+ (Safari is not currently supported)

## Repository Structure

```
.
├── server/
│   └── wt_oschub.py       # Hub relay server
├── bridge-local/
│   └── bridge.js          # Local UDP-WebSocket bridge (Option B)
├── client-web/
│   └── index.html         # Web client interface (Option B)
├── local.py               # Python CLI bridge (Option A — no browser needed)
├── .gitignore             # Git ignore settings
├── LICENSE                # GNU GPL v3 License
└── README.md              # Project documentation
```

## Setup & Execution

### A. For the Hub Operator

Deploy `wt_oschub.py` on a public server:

```bash
cd server
pip install aioquic
python wt_oschub.py --cert /path/to/fullchain.pem --key /path/to/privkey.pem
```

Additional options (all optional):

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | 8443 | Hub listen port |
| `--no-rewrite` | — | Disable OSC address rewriting (pass frames verbatim) |
| `--max-msg-size` | 65536 | Max OSC message size in bytes per message |
| `--rate-limit` | 200 | Max messages per second per client |
| `--log-level` | INFO | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

Then host `index.html` on an HTTPS-enabled web server.

> **Note:** The Hub port defaults to `8443` and can be changed with `--port`. The Web Client now has a **Hub Port** input field (default: `8443`) — update it to match `--port` if changed. No need to edit `index.html`. The Hub server's hostname is automatically derived from `window.location.hostname` — no manual URL entry is needed as long as the Web server and Hub server run on the same machine. If they are on separate machines, edit `baseUrl` in `index.html` directly.

If the server runs Linux, systemd can be used to manage `wt_oschub.py` as a service and schedule daily restarts. Create the following two files:

`/etc/systemd/system/wt-oschub.service`:
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

`/etc/systemd/system/wt-oschub.timer`:
```ini
[Unit]
Description=Daily restart of WebTransport OSC Hub

[Timer]
OnCalendar=*-*-* 04:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Then enable and start both:
```bash
systemctl daemon-reload
systemctl enable --now wt-oschub.service
systemctl enable --now wt-oschub.timer
```

> **Note:** Adjust the `OnCalendar` time and the Python path (`which python3`) to match your environment.

### B. For the Session Manager

Share the Web Client URL and a unique Session ID with all participants.

### C. For Participants

#### 1. SuperCollider Setup

Download and install SuperCollider from [supercollider.github.io](https://supercollider.github.io) if you haven't already. Launch SuperCollider and boot the server.

Messages relayed from the hub arrive with their OSC address rewritten to `/remote/<sender_name>/<original_address>` (e.g. `/remote/alice/s_new`). This allows recipients to identify who sent each message and handle it explicitly via `OSCdef`.

The simplest setup is a single `OSCdef` that receives all remote messages, extracts the original address, and forwards them to scsynth:

```supercollider
// Receives all remote OSC messages from the hub.
// The address format is /remote/<sender_name>/<original_address>.
// Use OSCFunc.trace to inspect incoming messages during a session.
OSCdef(\remoteAll, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    // parts = ['remote', 'alice', 's_new', ...]
    var cmd = ("/" ++ parts[2..].join("/")).asSymbol;
    s.sendMsg(cmd, *msg[1..]);
}, nil);
```

To handle messages from a specific sender or command selectively:

```supercollider
// Handle /s_new from any remote participant
OSCdef(\remoteSNew, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    var senderName = parts[1];
    (senderName ++ " triggered /s_new").postln;
    s.sendMsg(\s_new, *msg[1..]);
}, nil);
```

> **Note:** OSC Bundles are fully supported. The hub parses each Bundle recursively, rewrites the address of every contained message to `/remote/<sender_name>/<original_address>`, and preserves the timetag. When a sender uses `sendBundle(delta, ...)`, sclang on the receiving end unpacks the Bundle and passes the timetag as the `time` argument to the OSCdef handler. To preserve the intended timing and forward it to scsynth as a Bundle, use `time` as follows:
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
> Since each participant's internal clock (`thisThread.seconds`) is independent, some drift is inevitable. Taking a sufficiently large delta (e.g. 5 seconds) helps absorb network latency and clock differences.

**Hub system notifications:** The hub sends two OSC messages that are delivered directly (not address-rewritten) to all participants:

- `/hub/join <name>` — sent when a new participant joins the session
- `/hub/leave <name>` — sent when a participant leaves

```supercollider
OSCdef(\hubJoin,  { |msg| ("→ " ++ msg[1] ++ " joined").postln }, '/hub/join');
OSCdef(\hubLeave, { |msg| ("← " ++ msg[1] ++ " left").postln  }, '/hub/leave');
```

You can also use other SC-compatible environments. Equivalent setup code for Python (Supriya) and Clojure (Overtone):

**Python (Supriya):**

```python
import threading
from pythonosc import dispatcher, osc_server
from pythonosc.udp_client import SimpleUDPClient

# Target: the local Node.js bridge
bridge = SimpleUDPClient("127.0.0.1", 57121)

# Receive /remote/* messages and relay the original command to scsynth
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

;; Target: the local Node.js bridge
(def bridge (osc-client "127.0.0.1" 57121))

;; Receive /remote/* messages and relay the original command to scsynth
(def receiver (osc-server 57120))
(osc-handle receiver "/remote/*"
  (fn [msg]
    (let [parts (clojure.string/split (:path msg) #"/")
          cmd (str "/" (clojure.string/join "/" (drop 3 parts)))]
      (apply snd cmd (:args msg)))))
```

#### 2. Local Bridge Setup

```bash
cd bridge-local
npm install ws
node bridge.js
```

Options (all optional, defaults shown):

| Option | Default | Description |
|--------|---------|-------------|
| `--sc-port` | 57120 | Port where SC/sclang receives OSC |
| `--osc-port` | 57121 | Local UDP port the bridge listens on for OSC from SC |
| `--ws-port` | 8080 | WebSocket port the bridge exposes to the browser |

#### Alternative: Python CLI Bridge (local.py)

`local.py` replaces both bridge.js and index.html in a single Python script. No browser or Node.js is required.

```bash
pip install aioquic
python local.py your-hub-server.com --session my-session
```

Options:

| Option | Default | Description |
|--------|---------|-------------|
| `server` | *(required)* | Hub server hostname |
| `--port` | 8443 | Hub server port |
| `--sc-port` | 57120 | SC receive port |
| `--osc-port` | 57121 | Local OSC receive port |
| `--session` | *(prompted)* | Session ID to join |
| `--name` | *(optional)* | Your display name |
| `--insecure` | — | Disable TLS certificate verification (for self-signed certs) |

On connect, the console prints your assigned name and ID. OSC routing (datagram vs. stream) follows the same rules as the browser client. If the connection drops, the bridge reconnects automatically with exponential backoff (1 s → 30 s).

> **Note:** When using `local.py`, send OSC to port 57121 (the `--osc-port`) instead of using the browser. Set `~bridge = NetAddr("127.0.0.1", 57121)` in SC as you would with bridge.js.

#### 3. Web Connection

Open the Web Client URL in a WebTransport-capable browser. Enter the Session ID, optionally your display name (must not contain `/`), the Hub Port (default: `8443`, must match `--port`), and the Bridge Port (default: `8080`, must match `--ws-port`). Then click **Connect All**. Your Client ID and display name will be shown once connected. If the connection drops, the client reconnects automatically with exponential backoff (1 s → 30 s).

#### 4. Sending OSC Messages

Once all participants are connected, OSC messages sent to `~bridge` are relayed to all participants' scsynth instances. Below is a basic example using sclang:

> **Note:** Node IDs are shared across all participants in a session. Using the same ID (e.g., `11000`) from multiple participants will cause conflicts — one participant's `/n_set` or `/n_free` will affect another's node. Consider partitioning ID ranges per participant (e.g. derived from client ID), using Groups (`/g_new`) to isolate each participant's nodes, or designating a single sender who controls all node IDs.

```supercollider
// Target: the local Node.js bridge
~bridge = NetAddr("127.0.0.1", 57121);

// Define and send a SynthDef
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

~bridge.sendMsg(\d_recv, ~def.asBytes);

// Wait a moment for all participants to load the SynthDef, then trigger a note
~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);

// Change a parameter value
~bridge.sendMsg(\n_set, 11000, \freq, 648);

// Free the node
~bridge.sendMsg(\n_free, 11000);
```

Equivalent sending code for Python (Supriya) and Clojure (Overtone):

**Python (Supriya):**

```python
# Define a SynthDef and compile to bytes
@synthdef()
def sine_synth(freq=440, amp=0.2):
    sig = SinOsc.ar(frequency=freq) * amp
    Out.ar(bus=0, source=Pan2.ar(sig))

bridge.send_message("/d_recv", [sine_synth.compile()])

# Wait a moment for all participants to load the SynthDef, then trigger a note
bridge.send_message("/s_new", ["sine-synth", 11000, 0, 1, "freq", 432])

# Change a parameter value
bridge.send_message("/n_set", [11000, "freq", 648])

# Free the node
bridge.send_message("/n_free", [11000])
```

**Clojure (Overtone):**

```clojure
;; Define a SynthDef
(defsynth sine-synth [freq 440 amp 0.2]
  (out 0 (pan2 (* amp (sin-osc freq)))))

(osc-send bridge "/d_recv" (synthdef-bytes (:sdef sine-synth)))

;; Wait a moment for all participants to load the SynthDef, then trigger a note
(osc-send bridge "/s_new" "sine-synth" 11000 0 1 "freq" 432)

;; Change a parameter value
(osc-send bridge "/n_set" 11000 "freq" 648)

;; Free the node
(osc-send bridge "/n_free" 11000)
```

> **Note:** `synthdef-bytes` is provided by `overtone.sc.machinery.synthdef` and serializes the SynthDef into the binary format that scsynth expects.

## Technical Notes

### Traffic Routing

Messages are routed to **WebTransport Streams** if:
- The message is an **OSC Bundle** (always sent via Stream for reliable timetag delivery)
- OSC address starts with `/d_` (SynthDef), `/b_` (Buffer), or `/sy` (Sync — for reliable delivery of async command synchronization)
- Data size exceeds 1000 bytes

Otherwise, **Datagrams** are used for minimum latency.

### Synchronizing Async Commands

scsynth processes many commands asynchronously — including `/d_recv` (SynthDef loading), `/b_alloc` (buffer allocation), and `/b_gen` (buffer generation). A simple `/sync` from the sender only confirms that the **sender's own scsynth** has finished processing its queue — not that all remote participants are ready.

`/sync` can be applied uniformly to any combination of async commands. For example, to ensure all participants have both loaded a SynthDef and filled a buffer before playback:

```supercollider
~bridge.sendMsg(\d_recv, ~def.asBytes);       // async: load SynthDef
~bridge.sendMsg(\b_alloc, 0, 1024, 1);        // async: allocate buffer (1024 frames)
~bridge.sendMsg(\b_gen, 0, \sine1, 0, 1.0/1, 1.0/2, 1.0/3, 1.0/4, 1.0/5, 1.0/6);  // async: fill with additive sine partials
~bridge.sendMsg(\sync, 5678);                 // wait for all of the above
```

A more robust approach is possible using `/who` and client IDs. The flow is as follows:

1. Each participant runs the setup code below before the session starts. When `/sync` arrives, it forwards it to their own scsynth and broadcasts `/synced` back through the hub once their scsynth confirms the queue is complete. `thisProcess.addOSCRecvFunc` is used here for the same reason as the general relay handler — `OSCdef` cannot filter by port reliably.
2. The sender queries `/who` to learn the number of participants, then sends the async commands followed by `/sync`.
3. The sender counts incoming `/synced` replies and proceeds only when all participants have responded.

**Participant setup (run before session, sclang):**

```supercollider
// When /remote/*/sync arrives from the hub, forward to local scsynth
// and broadcast /synced back through the hub once the queue is complete.
OSCdef(\forwardSync, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    if((parts.size >= 3) && (parts[2] == 'sync'), {
        var syncId = msg[1];
        OSCdef(\waitAndReply, {|msg2|
            // scsynth replies: ['/done', '/sync', syncId]
            if((msg2[1] == '/sync') && (msg2[2] == syncId), {
                ~bridge.sendMsg('/synced', syncId);  // broadcast via hub
                OSCdef(\waitAndReply).free;
            });
        }, '/done');
        s.sendMsg('/sync', syncId);  // forward to local scsynth
    });
}, nil);
```

**Sender workflow (sclang):**

```supercollider
~bridge = NetAddr("127.0.0.1", 57121);
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

// Step 1: query participant count
OSCdef(\whoReply, {|msg|
    var count = msg.size - 1;  // msg[0] is '/who/reply', rest are participant names
    var received = 0;

    // Step 3: count /synced replies from all participants
    OSCdef(\collectSynced, {|msg2|
        received = received + 1;
        if(received >= count, {
            ~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);
            OSCdef(\collectSynced).free;
        });
    }, '/synced');

    // Step 2: send async commands and /sync
    ~bridge.sendMsg(\d_recv, ~def.asBytes);
    ~bridge.sendMsg(\sync, 1234);

    OSCdef(\whoReply).free;
}, '/who/reply');

~bridge.sendMsg('/who');
```

> **Note:** `/synced` replies from participants are broadcast through the hub and received by the sender's `OSCdef(\collectSynced)` on port 57120. The sender's own `/synced` (from their local scsynth via `\forwardSync`) is also counted, so `count` should reflect all participants including the sender if they too run `\forwardSync`.

### Node Management and FAILURE IN SERVER Messages

When remote participants send OSC commands such as `/s_new` or `/n_free`, sclang's Post window may display messages like:

```
FAILURE IN SERVER /n_free Node 11000 not found
FAILURE IN SERVER /s_new duplicate node ID
```

These appear because sclang maintains its own internal node management table, which is updated by feedback messages (such as `/n_end`) that scsynth sends back to the client that issued the command. When commands arrive via the hub from remote participants, scsynth's feedback is not routed back through the hub to each participant's sclang — so sclang's table diverges from the actual state of scsynth.

The important caveat is that **these messages alone do not indicate whether scsynth has processed the command correctly or not**. A `FAILURE IN SERVER` message may reflect a genuine error on scsynth (such as a duplicate node ID caused by two participants using the same ID), or it may simply be a consequence of sclang's table being out of sync with scsynth's actual state. The message text does not distinguish between the two.

To check the actual state of scsynth directly, use:

```supercollider
s.queryAllNodes;
```

### Buffer Usage and Sample Sharing

For wavetable or short generative buffers (e.g. additive synthesis via `/b_gen`), sending `/b_alloc` and `/b_gen` through the hub works well — these involve only small amounts of parameter data and complete quickly on each participant's scsynth.

For pre-recorded audio samples, transferring the actual audio data through the hub is not recommended. Audio files are typically large, and routing them through WebTransport would introduce significant latency and may strain the connection. Instead, distribute sample files to all participants before the session (e.g. via file sharing) and have each participant load them locally using `/b_allocRead`:

```supercollider
// Each participant loads the sample locally — not sent through the hub
s.sendMsg(\b_allocRead, 0, "/path/to/shared-sample.wav");
```

`/sync` can still be used to confirm that all participants have finished loading before playback begins.

### TLS Certificates

WebTransport requires a valid TLS certificate. For public servers, [Let's Encrypt](https://letsencrypt.org) is recommended. Note that **Cloudflare Origin CA certificates are not currently compatible** with WebTransport and will cause connection errors. For local development, launch Chrome with:

```
--origin-to-force-quic-on=yourdomain.com:8443
```

### Firewall / Port Requirements

The following ports must be open on the Hub server:

| Port | Protocol | Purpose |
|------|----------|---------|
| 8443 (or custom) | **UDP** | WebTransport (QUIC/HTTP3) — the Hub's main port. Change with `--port`. |
| 80 | TCP | Let's Encrypt HTTP-01 challenge (certificate issuance and renewal). Not required if using DNS-01 challenge or a pre-issued certificate. |
| 443 | TCP | HTTPS for hosting `index.html`. Not required if hosted on a separate server. |

> **Note:** WebTransport runs over QUIC, which uses **UDP** — not TCP. Make sure your firewall allows UDP traffic on the Hub port, as this is often overlooked.

## License

This project is licensed under the GNU GPL v3 — see the [LICENSE](LICENSE) file for details.

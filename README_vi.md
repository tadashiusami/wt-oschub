# WebTransport OSC Hub

Hệ thống relay OSC hai chiều, độ trễ thấp dành cho SuperCollider sử dụng WebTransport (HTTP/3).

## Tính năng

- **Cơ sở hạ tầng Hybrid**: Relay dữ liệu qua trình duyệt hỗ trợ WebTransport, sử dụng Node.js bridge để tích hợp môi trường SuperCollider của mỗi người tham gia.
- **Python CLI Bridge**: `local.py` cung cấp kết nối tương tự bridge.js + trình duyệt trong một script Python duy nhất — không cần trình duyệt.
- **Truyền tải Hybrid**: Tự động chuyển đổi giữa Datagram (cho dữ liệu biểu diễn tốc độ cao) và Stream (cho việc truyền SynthDef/Buffer đáng tin cậy).
- **Cô lập Session**: Hỗ trợ nhiều session độc lập sử dụng Session ID.
- **Thông báo Tham gia/Rời khỏi**: Hub phát `/hub/join <name>` và `/hub/leave <name>` khi người tham gia vào hoặc rời khỏi session.
- **Chế độ Không-Viết-Lại**: Flag `--no-rewrite` truyền các frame OSC nguyên vẹn mà không viết lại địa chỉ.

## Kiến trúc Hệ thống

| Thành phần | Mô tả |
|-----------|-------|
| **Hub Server** (`wt_oschub.py`) | Server Python (aioquic) relay OSC giữa các client |
| **Python Bridge** (`local.py`) | Python CLI bridge — kết nối SC trực tiếp với Hub (không cần trình duyệt) |
| **Web Client** (`index.html`) | Transport dựa trên trình duyệt kết nối với Hub |
| **Local Bridge** (`bridge.js`) | Node.js bridge kết nối SuperCollider (UDP) và Web Client (WebSocket) |

## Demo

Một Hub demo công cộng có sẵn tại `connect.oschub.asia` (cổng `8443`). Lưu ý rằng server này có thể không phải lúc nào cũng có thể truy cập được.

- **Web Client**: Mở [https://connect.oschub.asia/](https://connect.oschub.asia/) trong trình duyệt hỗ trợ WebTransport
- **Python CLI Bridge**: `python local.py connect.oschub.asia --session your-session`

## Yêu cầu

### Dành cho Operator Hub
- Python 3.10+
- Server công cộng với IP cố định hoặc Domain
- Chứng chỉ TLS hợp lệ (ví dụ: Let's Encrypt)

### Dành cho Người tham gia
- SuperCollider (bất kỳ môi trường nào sử dụng scsynth làm audio engine)
- **Tùy chọn A — Python CLI Bridge** (`local.py`): Python 3.10+ và `pip install aioquic`
- **Tùy chọn B — Trình duyệt + Node.js Bridge**: Node.js (để chạy `bridge.js`) và trình duyệt hỗ trợ WebTransport: Chrome 97+, Edge 98+, Firefox 115+, Opera 83+ (Safari hiện chưa được hỗ trợ)

## Cấu trúc Repository

```
.
├── server/
│   └── wt_oschub.py       # Hub relay server
├── bridge-local/
│   └── bridge.js          # Local UDP-WebSocket bridge (Tùy chọn B)
├── client-web/
│   └── index.html         # Giao diện web client (Tùy chọn B)
├── local.py               # Python CLI bridge (Tùy chọn A — không cần trình duyệt)
├── .gitignore
├── LICENSE                # GNU GPL v3
└── README.md
```

## Cài đặt & Chạy

### A. Dành cho Operator Hub

Deploy `wt_oschub.py` trên server công cộng:

```bash
cd server
pip install aioquic
python wt_oschub.py --cert /path/to/fullchain.pem --key /path/to/privkey.pem
```

Các tùy chọn bổ sung (tất cả đều tùy chọn):

| Tùy chọn | Mặc định | Mô tả |
|----------|----------|-------|
| `--port` | 8443 | Cổng lắng nghe của hub |
| `--no-rewrite` | — | Tắt tính năng viết lại địa chỉ OSC (chuyển tiếp frame nguyên vẹn) |
| `--max-msg-size` | 65536 | Kích thước tin nhắn OSC tối đa tính bằng byte |
| `--rate-limit` | 200 | Số tin nhắn tối đa mỗi giây mỗi client |
| `--log-level` | INFO | Mức độ log: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

Sau đó host `index.html` trên web server có hỗ trợ HTTPS.

> **Lưu ý:** Cổng Hub mặc định là `8443` và có thể thay đổi bằng `--port`. Web Client hiện có trường nhập **Hub Port** (mặc định: `8443`) — cập nhật để khớp với `--port` nếu thay đổi. Không cần sửa `index.html`. Hostname của Hub server được tự động lấy từ `window.location.hostname` — không cần nhập URL thủ công miễn là Web server và Hub server chạy trên cùng máy. Nếu ở máy khác nhau, hãy chỉnh `baseUrl` trong `index.html` trực tiếp.

Nếu server chạy Linux, có thể dùng systemd để quản lý `wt_oschub.py` như một service và lên lịch khởi động lại hàng ngày. Tạo hai file sau:

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

Sau đó enable và start cả hai:
```bash
systemctl daemon-reload
systemctl enable --now wt-oschub.service
systemctl enable --now wt-oschub.timer
```

> **Lưu ý:** Điều chỉnh thời gian `OnCalendar` và đường dẫn Python (`which python3`) cho phù hợp với môi trường của bạn.

### B. Dành cho Session Manager

Chia sẻ URL Web Client và Session ID duy nhất với tất cả người tham gia. Session ID không được vượt quá 64 ký tự.

### C. Dành cho Người tham gia

#### 1. Cài đặt SuperCollider

Tải và cài đặt SuperCollider từ [supercollider.github.io](https://supercollider.github.io) nếu chưa có. Khởi chạy SuperCollider và boot server.

Các tin nhắn được relay từ hub đến với địa chỉ OSC được viết lại thành `/remote/<sender_name>/<original_address>` (ví dụ: `/remote/alice/s_new`). Điều này cho phép người nhận xác định ai đã gửi mỗi tin nhắn và xử lý nó tường minh qua `OSCdef`.

Cài đặt đơn giản nhất là `thisProcess.addOSCRecvFunc` nhận tất cả tin nhắn từ xa, trích xuất địa chỉ gốc và chuyển tiếp chúng đến scsynth. Không thể dùng `OSCdef` ở đây vì nó khớp địa chỉ OSC theo chuỗi chính xác — `/remote` sẽ không khớp với `/remote/alice/s_new`. Lưu hàm trong biến để có thể xóa sau nếu cần.

Cổng nhận (`57120`) được lọc tường minh để tránh xung đột với các ứng dụng OSC khác cùng dùng chung instance sclang — ví dụ SuperDirt đăng ký handler riêng và có thể gây nhiễu nếu không lọc. Cổng gửi không được lọc vì `local.py` dùng cổng UDP được gán động.

Tin nhắn `/ping` được hub xử lý và trả về cho người gửi dưới dạng `/ping/reply` — không broadcast đến người tham gia khác. Handler relay bên dưới không cần loại trừ `/ping` một cách tường minh.

```supercollider
// Store in a variable so it can be removed with thisProcess.removeOSCRecvFunc(~remoteFunc)
~remoteFunc = {|msg, time, addr, recvPort|
    if((addr.ip == "127.0.0.1") && (recvPort == 57120), {
        if(msg[0].asString.beginsWith("/remote/"), {
            var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
            var cmd = ("/" ++ parts[2..].join("/")).asSymbol;
            var delta = time - thisThread.seconds;
            if(delta > 0, {
                s.sendBundle(delta, [cmd] ++ msg[1..]);
            }, {
                s.sendMsg(cmd, *msg[1..]);
            });
        });
    });
};

thisProcess.addOSCRecvFunc(~remoteFunc);
```

Để xóa handler:

```supercollider
thisProcess.removeOSCRecvFunc(~remoteFunc);
```

Để xử lý có chọn lọc tin nhắn từ người gửi hoặc lệnh cụ thể, kiểm tra `parts[1]` (tên người gửi) hoặc `cmd` bên trong handler:

```supercollider
~remoteFunc = {|msg, time, addr, recvPort|
    if((addr.ip == "127.0.0.1") && (recvPort == 57120), {
        if(msg[0].asString.beginsWith("/remote/"), {
            var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
            var senderName = parts[1];
            var cmd = ("/" ++ parts[2..].join("/")).asSymbol;
            // example: log sender and command
            (senderName ++ " -> " ++ cmd).postln;
            var delta = time - thisThread.seconds;
            if(delta > 0, {
                s.sendBundle(delta, [cmd] ++ msg[1..]);
            }, {
                s.sendMsg(cmd, *msg[1..]);
            });
        });
    });
};
```

> **Lưu ý:** OSC Bundle được hỗ trợ đầy đủ. Hub phân tích từng Bundle đệ quy, viết lại địa chỉ của mỗi tin nhắn chứa trong đó thành `/remote/<sender_name>/<original_address>`, và giữ nguyên timetag. Khi người gửi dùng `sendBundle(delta, ...)`, sclang ở phía nhận sẽ unpack Bundle và truyền timetag làm đối số `time`. Handler trên đã xử lý điều này qua `time - thisThread.seconds` — không cần cài đặt thêm. Vì đồng hồ nội bộ của mỗi người tham gia (`thisThread.seconds`) là độc lập, một số drift là không thể tránh khỏi. Dùng delta đủ lớn (ví dụ: 5 giây) giúp hấp thụ độ trễ mạng và sự khác biệt đồng hồ.

**Thông báo hệ thống hub:** Hub gửi hai tin nhắn OSC trực tiếp (không viết lại địa chỉ) đến tất cả người tham gia:

- `/hub/join <name>` — gửi khi người tham gia mới vào session
- `/hub/leave <name>` — gửi khi người tham gia rời khỏi session

```supercollider
OSCdef(\hubJoin,  { |msg| ("→ " ++ msg[1] ++ " đã tham gia").postln }, '/hub/join');
OSCdef(\hubLeave, { |msg| ("← " ++ msg[1] ++ " đã rời khỏi").postln  }, '/hub/leave');
```

Bạn cũng có thể dùng các môi trường tương thích SC khác. Code cài đặt tương đương cho Python (Supriya) và Clojure (Overtone):

**Python (Supriya):**

```python
import threading
from pythonosc import dispatcher, osc_server
from pythonosc.udp_client import SimpleUDPClient

# Mục tiêu: local Node.js bridge
bridge = SimpleUDPClient("127.0.0.1", 57121)

# Nhận tin nhắn /remote/* và relay lệnh gốc đến scsynth
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

;; Mục tiêu: local Node.js bridge
(def bridge (osc-client "127.0.0.1" 57121))

;; Nhận tin nhắn /remote/* và relay lệnh gốc đến scsynth
(def receiver (osc-server 57120))
(osc-handle receiver "/remote/*"
  (fn [msg]
    (let [parts (clojure.string/split (:path msg) #"/")
          cmd (str "/" (clojure.string/join "/" (drop 3 parts)))]
      (apply snd cmd (:args msg)))))
```

#### 2. Cài đặt Local Bridge

```bash
cd bridge-local
npm install ws
node bridge.js
```

Các tùy chọn (tất cả đều tùy chọn, hiển thị giá trị mặc định):

| Tùy chọn | Mặc định | Mô tả |
|----------|----------|-------|
| `--sc-port` | 57120 | Cổng SC/sclang nhận OSC |
| `--osc-port` | 57121 | Cổng UDP cục bộ bridge lắng nghe cho OSC từ SC |
| `--ws-port` | 8080 | Cổng WebSocket bridge để lộ ra cho trình duyệt |

#### Thay thế: Python CLI Bridge (local.py)

`local.py` thay thế cả bridge.js và index.html trong một script Python duy nhất. Không cần trình duyệt hay Node.js.

```bash
pip install aioquic
python local.py your-hub-server.com --session my-session
```

Các tùy chọn:

| Tùy chọn | Mặc định | Mô tả |
|----------|----------|-------|
| `server` | *(bắt buộc)* | Hostname của hub server |
| `--port` | 8443 | Cổng của hub server |
| `--sc-port` | 57120 | Cổng nhận của SC |
| `--osc-port` | 57121 | Cổng nhận OSC cục bộ |
| `--session` | *(được hỏi)* | ID session muốn tham gia |
| `--name` | *(tùy chọn)* | Tên hiển thị của bạn |
| `--insecure` | — | Tắt xác minh chứng chỉ TLS (dành cho chứng chỉ tự ký) |

Khi kết nối, console hiển thị tên và ID được cấp. OSC routing (datagram hay stream) tuân theo cùng quy tắc với browser client. Nếu kết nối bị ngắt, bridge tự động kết nối lại với exponential backoff (1s → 30s).

> **Lưu ý:** Khi dùng `local.py`, gửi OSC đến port 57121 (the `--osc-port`) thay vì dùng trình duyệt. Đặt `~bridge = NetAddr("127.0.0.1", 57121)` trong SC như với bridge.js.

#### 3. Kết nối Web

Mở URL Web Client trong trình duyệt hỗ trợ WebTransport. Nhập Session ID (không được vượt quá 64 ký tự), tùy chọn tên hiển thị (không được chứa `/` hoặc vượt quá 64 ký tự), Hub Port (mặc định: `8443`, phải khớp với `--port`), và Bridge Port (mặc định: `8080`, phải khớp với `--ws-port`). Sau đó nhấp **Connect All**. Client ID và tên hiển thị sẽ được hiển thị khi kết nối. Nếu kết nối bị ngắt, client tự động kết nối lại với exponential backoff (1s → 30s).

#### 4. Gửi Tin nhắn OSC

Khi tất cả người tham gia đã kết nối, tin nhắn OSC gửi đến `~bridge` sẽ được relay đến tất cả scsynth instance của người tham gia. Dưới đây là ví dụ cơ bản dùng sclang:

> **Lưu ý:** Node ID được chia sẻ giữa tất cả người tham gia trong một session. Dùng cùng ID (ví dụ: `11000`) từ nhiều người tham gia sẽ gây xung đột — `/n_set` hoặc `/n_free` của một người có thể ảnh hưởng đến node của người khác. Hãy xem xét việc phân vùng phạm vi ID theo từng người tham gia (ví dụ: dựa từ client ID), dùng Group (`/g_new`) để cô lập node của mỗi người, hoặc chỉ định một người gửi duy nhất kiểm soát tất cả node ID.

```supercollider
// Mục tiêu: local Node.js bridge
~bridge = NetAddr("127.0.0.1", 57121);

// Định nghĩa và gửi SynthDef
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

~bridge.sendMsg(\d_recv, ~def.asBytes);

// Chờ một chút để tất cả người tham gia load SynthDef, rồi trigger một nốt
~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);

// Thay đổi giá trị tham số
~bridge.sendMsg(\n_set, 11000, \freq, 648);

// Giải phóng node
~bridge.sendMsg(\n_free, 11000);
```

Code gửi tương đương cho Python (Supriya) và Clojure (Overtone):

**Python (Supriya):**

```python
# Định nghĩa SynthDef và compile thành bytes
@synthdef()
def sine_synth(freq=440, amp=0.2):
    sig = SinOsc.ar(frequency=freq) * amp
    Out.ar(bus=0, source=Pan2.ar(sig))

bridge.send_message("/d_recv", [sine_synth.compile()])

# Chờ một chút để tất cả người tham gia load SynthDef, rồi trigger một nốt
bridge.send_message("/s_new", ["sine-synth", 11000, 0, 1, "freq", 432])

# Thay đổi giá trị tham số
bridge.send_message("/n_set", [11000, "freq", 648])

# Giải phóng node
bridge.send_message("/n_free", [11000])
```

**Clojure (Overtone):**

```clojure
;; Định nghĩa SynthDef
(defsynth sine-synth [freq 440 amp 0.2]
  (out 0 (pan2 (* amp (sin-osc freq)))))

(osc-send bridge "/d_recv" (synthdef-bytes (:sdef sine-synth)))

;; Chờ một chút để tất cả người tham gia load SynthDef, rồi trigger một nốt
(osc-send bridge "/s_new" "sine-synth" 11000 0 1 "freq" 432)

;; Thay đổi giá trị tham số
(osc-send bridge "/n_set" 11000 "freq" 648)

;; Giải phóng node
(osc-send bridge "/n_free" 11000)
```

> **Lưu ý:** `synthdef-bytes` được cung cấp bởi `overtone.sc.machinery.synthdef` và serialize SynthDef sang định dạng binary mà scsynth mong đợi.

#### 5. Đo độ trễ (/ping)

Bất kỳ người tham gia nào cũng có thể đo độ trễ round-trip bằng cách gửi tin nhắn `/ping` kèm timestamp. Hub sẽ phản hồi lại dưới dạng `/ping/reply` với tất cả argument được giữ nguyên. Lưu ý rằng `local.py` gửi keepalive `/ping` không có argument mỗi 20 giây — hãy lọc bằng cách kiểm tra `msg.size > 1`:

```supercollider
// Đo độ trễ liên tục và cập nhật ~latency mỗi 2 giây
~pingTimes = Array.newClear(10);
~pingIndex = 0;

OSCdef(\pingReply, { |msg|
    if(msg.size > 1, {  // bỏ qua keepalive ping (không có timestamp arg)
        var rtt = Date.getDate.rawSeconds - msg[1].asFloat;
        var latency = rtt / 2;
        ~pingTimes[~pingIndex % 10] = latency;
        ~pingIndex = ~pingIndex + 1;
        if(~pingIndex >= 10) {
            var valid = ~pingTimes.select({ |v| v.notNil });
            ~latency = valid.maxItem * 1.5;  // trường hợp tệ nhất × 1.5 biên an toàn
            ("latency updated: " ++ ~latency.round(0.001) ++ "s").postln;
        };
    });
}, '/ping/reply');

~pingRoutine = Routine({
    loop {
        ~bridge.sendMsg('/ping', Date.getDate.rawSeconds);
        2.wait;
    };
}).play(SystemClock);

// Dừng ping:
// ~pingRoutine.stop;
```

## Ghi chú Kỹ thuật

### Định tuyến Traffic

Tin nhắn được định tuyến đến **WebTransport Stream** nếu:
- Tin nhắn là **OSC Bundle** (luôn gửi qua Stream để đảm bảo timetag đáng tin cậy)
- Địa chỉ OSC bắt đầu bằng `/d_` (SynthDef), `/b_` (Buffer), hoặc `/sy` (Sync — để đảm bảo delivery đáng tin cậy khi đồng bộ async command)
- Kích thước dữ liệu vượt quá 1000 byte

Ngược lại, **Datagram** được dùng để giảm thiểu độ trễ.

### Đồng bộ Lệnh Async

scsynth xử lý nhiều lệnh bất đồng bộ — bao gồm `/d_recv` (tải SynthDef), `/b_alloc` (cấp phát buffer), và `/b_gen` (tạo buffer). Một `/sync` đơn giản từ người gửi chỉ xác nhận rằng **scsynth của chính người gửi** đã hoàn thành xử lý hàng đợi — không phải tất cả người tham gia từ xa đã sẵn sàng.

`/sync` có thể áp dụng đồng đều cho bất kỳ tổ hợp lệnh async nào. Ví dụ, để đảm bảo tất cả người tham gia đã tải SynthDef và điền buffer trước khi phát:

```supercollider
~bridge.sendMsg(\d_recv, ~def.asBytes);       // async: tải SynthDef
~bridge.sendMsg(\b_alloc, 0, 1024, 1);        // async: cấp phát buffer (1024 frame)
~bridge.sendMsg(\b_gen, 0, \sine1, 0, 1.0/1, 1.0/2, 1.0/3, 1.0/4, 1.0/5, 1.0/6);  // async: điền với sine partial cộng hưởng
~bridge.sendMsg(\sync, 5678);                 // chờ tất cả những điều trên
```

Cách tiếp cận mạnh mẽ hơn là sử dụng `/who` và client ID. Luồng như sau:

1. Mỗi người tham gia chạy code cài đặt bên dưới trước khi session bắt đầu. Khi `/sync` đến, họ chuyển tiếp đến scsynth của mình và broadcast `/synced` trở lại qua hub khi scsynth xác nhận hàng đợi đã hoàn thành. `thisProcess.addOSCRecvFunc` được dùng ở đây vì lý do tương tự như relay handler chung — `OSCdef` không thể lọc theo port một cách đáng tin cậy.
2. Người gửi query `/who` để biết số người tham gia, rồi gửi các lệnh async tiếp theo là `/sync`.
3. Người gửi đếm các phản hồi `/synced` đến và chỉ tiến hành khi tất cả người tham gia đã phản hồi.

**Cài đặt người tham gia (chạy trước session, sclang):**

```supercollider
// Khi /remote/*/sync đến từ hub, chuyển tiếp đến local scsynth
// và broadcast /synced trở lại qua hub khi hàng đợi hoàn thành.
OSCdef(\forwardSync, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    if((parts.size >= 3) && (parts[2] == 'sync'), {
        var syncId = msg[1];
        OSCdef(\waitAndReply, {|msg2|
            // scsynth phản hồi: ['/done', '/sync', syncId]
            if((msg2[1] == '/sync') && (msg2[2] == syncId), {
                ~bridge.sendMsg('/synced', syncId);  // broadcast qua hub
                OSCdef(\waitAndReply).free;
            });
        }, '/done');
        s.sendMsg('/sync', syncId);  // chuyển tiếp đến local scsynth
    });
}, nil);
```

**Workflow người gửi (sclang):**

```supercollider
~bridge = NetAddr("127.0.0.1", 57121);
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

// Bước 1: query số người tham gia
OSCdef(\whoReply, {|msg|
    var count = msg.size - 1;  // msg[0] là '/who/reply', còn lại là tên người tham gia
    var received = 0;

    // Bước 3: đếm phản hồi /synced từ tất cả người tham gia
    OSCdef(\collectSynced, {|msg2|
        received = received + 1;
        if(received >= count, {
            ~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);
            OSCdef(\collectSynced).free;
        });
    }, '/synced');

    // Bước 2: gửi lệnh async và /sync
    ~bridge.sendMsg(\d_recv, ~def.asBytes);
    ~bridge.sendMsg(\sync, 1234);

    OSCdef(\whoReply).free;
}, '/who/reply');

~bridge.sendMsg('/who');
```

> **Lưu ý:** Phản hồi `/synced` từ người tham gia được broadcast qua hub và nhận bởi `OSCdef(\collectSynced)` của người gửi trên port 57120. `/synced` của chính người gửi (từ local scsynth qua `\forwardSync`) cũng được tính, vì vậy `count` nên phản ánh tất cả người tham gia bao gồm người gửi nếu họ cũng chạy `\forwardSync`.

### Quản lý Node và Tin nhắn FAILURE IN SERVER

Khi người tham gia từ xa gửi lệnh OSC như `/s_new` hoặc `/n_free`, cửa sổ Post của sclang có thể hiển thị tin nhắn như:

```
FAILURE IN SERVER /n_free Node 11000 not found
FAILURE IN SERVER /s_new duplicate node ID
```

Những điều này xuất hiện vì sclang duy trì bảng quản lý node nội bộ của riêng mình, được cập nhật bởi các tin nhắn phản hồi (như `/n_end`) mà scsynth gửi lại cho client phát hành lệnh. Khi lệnh đến qua hub từ người tham gia từ xa, phản hồi của scsynth không được định tuyến trở lại qua hub đến sclang của mỗi người tham gia — vì vậy bảng của sclang phân kỳ với trạng thái thực tế của scsynth.

Điều quan trọng cần lưu ý là **những tin nhắn này một mình không cho biết scsynth có xử lý lệnh đúng hay không**. Tin nhắn `FAILURE IN SERVER` có thể phản ánh lỗi thực sự trên scsynth (chẳng hạn như node ID trùng lặp do hai người tham gia dùng cùng ID), hoặc có thể chỉ đơn giản là hậu quả của bảng sclang không đồng bộ với trạng thái thực tế của scsynth. Văn bản tin nhắn không phân biệt hai trường hợp này.

Để kiểm tra trạng thái thực tế của scsynth trực tiếp, dùng:

```supercollider
s.queryAllNodes;
```

### Sử dụng Buffer và Chia sẻ Sample

Đối với wavetable hoặc buffer sinh ngắn (ví dụ: tổng hợp cộng hưởng qua `/b_gen`), việc gửi `/b_alloc` và `/b_gen` qua hub hoạt động tốt — chúng chỉ liên quan đến lượng nhỏ dữ liệu tham số và hoàn thành nhanh trên scsynth của mỗi người tham gia.

Đối với sample âm thanh được ghi trước, không khuyến nghị truyền dữ liệu âm thanh thực tế qua hub. File âm thanh thường lớn, và routing qua WebTransport sẽ gây độ trễ đáng kể và có thể làm căng kết nối. Thay vào đó, hãy phân phối file sample cho tất cả người tham gia trước session (ví dụ: qua chia sẻ file) và để mỗi người tải chúng cục bộ bằng `/b_allocRead`:

```supercollider
// Mỗi người tham gia tải sample cục bộ — không gửi qua hub
s.sendMsg(\b_allocRead, 0, "/path/to/shared-sample.wav");
```

`/sync` vẫn có thể được dùng để xác nhận tất cả người tham gia đã hoàn thành tải trước khi phát bắt đầu.

### Chứng chỉ TLS

WebTransport yêu cầu chứng chỉ TLS hợp lệ. Đối với server công cộng, khuyến nghị sử dụng [Let's Encrypt](https://letsencrypt.org). Lưu ý rằng **chứng chỉ Cloudflare Origin CA hiện không tương thích** với WebTransport và sẽ gây lỗi kết nối. Để phát triển cục bộ, khởi chạy Chrome với:

```
--origin-to-force-quic-on=yourdomain.com:8443
```

### Yêu cầu Firewall / Cổng

Các cổng sau phải mở trên Hub server:

| Cổng | Giao thức | Mục đích |
|------|-----------|---------|
| 8443 (hoặc tùy chỉnh) | **UDP** | WebTransport (QUIC/HTTP3) — cổng chính của Hub. Thay đổi bằng `--port`. |
| 80 | TCP | Let's Encrypt HTTP-01 challenge (cấp và gia hạn certificate). Không cần nếu dùng DNS-01 challenge hoặc certificate đã cấp. |
| 443 | TCP | HTTPS để host `index.html`. Không cần nếu host trên server riêng. |

> **Lưu ý:** WebTransport chạy trên QUIC, sử dụng **UDP** — không phải TCP. Đảm bảo firewall của bạn cho phép traffic UDP trên cổng Hub, vì điều này thường bị bỏ qua.

## Giấy phép

Dự án này được cấp phép theo GNU GPL v3 — xem file [LICENSE](LICENSE) để biết chi tiết.

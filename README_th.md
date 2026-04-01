# WebTransport OSC Hub

ระบบ relay OSC แบบสองทิศทาง ความหน่วงต่ำสำหรับ SuperCollider โดยใช้ WebTransport (HTTP/3)

## คุณสมบัติ

- **โครงสร้างพื้นฐาน Hybrid**: ส่งต่อข้อมูลผ่านเบราว์เซอร์ที่รองรับ WebTransport โดยใช้ Node.js bridge เพื่อรวมสภาพแวดล้อม SuperCollider ของผู้เข้าร่วมแต่ละคน
- **Python CLI Bridge**: `local.py` ให้การเชื่อมต่อแบบเดียวกับ bridge.js + เบราว์เซอร์ในสคริปต์ Python เดียว — ไม่ต้องใช้เบราว์เซอร์
- **การส่งข้อมูล Hybrid**: สลับโดยอัตโนมัติระหว่าง Datagram (สำหรับข้อมูลการแสดงความเร็วสูง) และ Stream (สำหรับการถ่ายโอน SynthDef/Buffer ที่เชื่อถือได้)
- **การแยกเซสชัน**: รองรับหลายเซสชันที่เป็นอิสระโดยใช้ Session ID
- **การแจ้งเตือนการเข้า/ออก**: Hub บรอดแคสต์ `/hub/join <name>` และ `/hub/leave <name>` เมื่อผู้เข้าร่วมเข้าหรือออกจากเซสชัน
- **โหมดไม่เขียนใหม่**: Flag `--no-rewrite` ส่ง OSC frame แบบ verbatim โดยไม่เขียนที่อยู่ใหม่

## สถาปัตยกรรมระบบ

| ส่วนประกอบ | คำอธิบาย |
|-----------|---------|
| **Hub Server** (`wt_oschub.py`) | Python server (aioquic) ที่ relay OSC ระหว่างไคลเอนต์ |
| **Python Bridge** (`local.py`) | Python CLI bridge — เชื่อมต่อ SC โดยตรงกับ Hub (ไม่ต้องใช้เบราว์เซอร์) |
| **Web Client** (`index.html`) | Transport ที่ใช้เบราว์เซอร์เชื่อมต่อกับ Hub |
| **Local Bridge** (`bridge.js`) | Node.js bridge ที่เชื่อมต่อ SuperCollider (UDP) และ Web Client (WebSocket) |

## เดโม

Hub เดโมสาธารณะพร้อมใช้งานที่ `connect.oschub.asia` (พอร์ต `8443`) โปรดทราบว่าเซิร์ฟเวอร์นี้อาจไม่พร้อมใช้งานตลอดเวลา

- **เว็บไคลเอนต์**: เปิด [https://connect.oschub.asia/](https://connect.oschub.asia/) ในเบราว์เซอร์ที่รองรับ WebTransport
- **Python CLI Bridge**: `python local.py connect.oschub.asia --session your-session`

## ข้อกำหนดเบื้องต้น

### สำหรับ Operator ของ Hub
- Python 3.10+
- เซิร์ฟเวอร์สาธารณะที่มี IP/Domain คงที่
- ใบรับรอง TLS ที่ถูกต้อง (เช่น Let's Encrypt)

### สำหรับผู้เข้าร่วม
- SuperCollider (สภาพแวดล้อมใดก็ได้ที่ใช้ scsynth เป็น audio engine)
- **ตัวเลือก A — Python CLI Bridge** (`local.py`): Python 3.10+ และ `pip install aioquic`
- **ตัวเลือก B — เบราว์เซอร์ + Node.js Bridge**: Node.js (สำหรับ `bridge.js`) และเว็บเบราว์เซอร์ที่รองรับ WebTransport: Chrome 97+, Edge 98+, Firefox 115+, Opera 83+ (Safari ยังไม่รองรับในขณะนี้)

## โครงสร้าง Repository

```
.
├── server/
│   └── wt_oschub.py       # Hub relay server
├── bridge-local/
│   └── bridge.js          # Local UDP-WebSocket bridge (ตัวเลือก B)
├── client-web/
│   └── index.html         # Web client interface (ตัวเลือก B)
├── local.py               # Python CLI bridge (ตัวเลือก A — ไม่ต้องใช้เบราว์เซอร์)
├── .gitignore
├── LICENSE                # GNU GPL v3
└── README.md
```

## การตั้งค่าและการรัน

### A. สำหรับ Operator ของ Hub

Deploy `wt_oschub.py` บนเซิร์ฟเวอร์สาธารณะ:

```bash
cd server
pip install aioquic
python wt_oschub.py --cert /path/to/fullchain.pem --key /path/to/privkey.pem
```

ตัวเลือกเพิ่มเติม (ทั้งหมดเป็นทางเลือก):

| ตัวเลือก | ค่าเริ่มต้น | คำอธิบาย |
|---------|------------|---------|
| `--port` | 8443 | พอร์ตที่ฮับรับฟัง |
| `--no-rewrite` | — | ปิดการเขียนที่อยู่ OSC ใหม่ (ส่ง frame แบบ verbatim) |
| `--max-msg-size` | 65536 | ขนาดข้อความ OSC สูงสุดเป็นไบต์ต่อข้อความ |
| `--rate-limit` | 200 | จำนวนข้อความสูงสุดต่อวินาทีต่อไคลเอนต์ |
| `--log-level` | INFO | ระดับ log: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

จากนั้น host `index.html` บน web server ที่รองรับ HTTPS

> **หมายเหตุ:** พอร์ต Hub ค่าเริ่มต้นคือ `8443` และสามารถเปลี่ยนได้ด้วย `--port` Web Client มีฟิลด์ป้อนข้อมูล **Hub Port** (ค่าเริ่มต้น: `8443`) แล้ว — อัปเดตให้ตรงกับ `--port` หากเปลี่ยนแปลง ไม่จำเป็นต้องแก้ไข `index.html` ชื่อโฮสต์ของ Hub server ถูกดึงมาจาก `window.location.hostname` โดยอัตโนมัติ — ไม่จำเป็นต้องป้อน URL ด้วยตนเองตราบใดที่ Web server และ Hub server ทำงานบนเครื่องเดียวกัน หากอยู่บนเครื่องต่างกัน ให้แก้ไข `baseUrl` ใน `index.html` โดยตรง

หากเซิร์ฟเวอร์รัน Linux สามารถใช้ systemd จัดการ `wt_oschub.py` เป็นบริการและกำหนดการรีสตาร์ทรายวันได้ สร้างสองไฟล์ต่อไปนี้:

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

จากนั้น enable และเริ่มต้นทั้งสอง:
```bash
systemctl daemon-reload
systemctl enable --now wt-oschub.service
systemctl enable --now wt-oschub.timer
```

> **หมายเหตุ:** ปรับเวลา `OnCalendar` และ Python path (`which python3`) ให้เหมาะกับสภาพแวดล้อมของคุณ

### B. สำหรับ Session Manager

แชร์ URL ของ Web Client และ Session ID ที่ไม่ซ้ำกันกับผู้เข้าร่วมทุกคน

### C. สำหรับผู้เข้าร่วม

#### 1. การตั้งค่า SuperCollider

ดาวน์โหลดและติดตั้ง SuperCollider จาก [supercollider.github.io](https://supercollider.github.io) หากยังไม่มี เปิด SuperCollider และบูตเซิร์ฟเวอร์

ข้อความที่ relay จากฮับจะมาพร้อมกับที่อยู่ OSC ที่เขียนใหม่เป็น `/remote/<sender_name>/<original_address>` (เช่น `/remote/alice/s_new`) ซึ่งช่วยให้ผู้รับสามารถระบุผู้ส่งของแต่ละข้อความและจัดการอย่างชัดเจนผ่าน `OSCdef`

การตั้งค่าที่ง่ายที่สุดคือ `OSCdef` เดียวที่รับข้อความ remote ทั้งหมด ดึงที่อยู่ต้นฉบับ และส่งต่อไปยัง scsynth:

```supercollider
// รับข้อความ OSC remote ทั้งหมดจากฮับ
// รูปแบบที่อยู่คือ /remote/<sender_name>/<original_address>
// ใช้ OSCFunc.trace เพื่อตรวจสอบข้อความที่เข้ามาระหว่างเซสชัน
OSCdef(\remoteAll, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    // parts = ['remote', 'alice', 's_new', ...]
    var cmd = ("/" ++ parts[2..].join("/")).asSymbol;
    s.sendMsg(cmd, *msg[1..]);
}, nil);
```

เพื่อจัดการข้อความจากผู้ส่งหรือคำสั่งเฉพาะ:

```supercollider
// จัดการ /s_new จากผู้เข้าร่วม remote ใดก็ได้
OSCdef(\remoteSNew, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    var senderName = parts[1];
    (senderName ++ " triggered /s_new").postln;
    s.sendMsg(\s_new, *msg[1..]);
}, nil);
```

> **หมายเหตุ:** OSC Bundle รองรับอย่างสมบูรณ์ ฮับแยกวิเคราะห์แต่ละ Bundle แบบ recursive เขียนที่อยู่ของทุกข้อความที่บรรจุอยู่ใหม่เป็น `/remote/<sender_name>/<original_address>` และเก็บ timetag ไว้ เมื่อผู้ส่งใช้ `sendBundle(delta, ...)` sclang ฝั่งรับจะแกะ Bundle และส่ง timetag เป็นอาร์กิวเมนต์ `time` ให้ OSCdef handler เพื่อรักษา timing ที่ตั้งใจไว้และส่งต่อไปยัง scsynth เป็น Bundle ให้ใช้ `time` ดังนี้:
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
> เนื่องจากนาฬิกาภายในของผู้เข้าร่วมแต่ละคน (`thisThread.seconds`) เป็นอิสระ drift บางส่วนจึงหลีกเลี่ยงไม่ได้ การใช้ delta ที่ใหญ่พอ (เช่น 5 วินาที) ช่วยดูดซับความหน่วงของเครือข่ายและความแตกต่างของนาฬิกา

**การแจ้งเตือนระบบ hub:** Hub ส่งข้อความ OSC สองรายการต่อไปนี้โดยตรง (ไม่เขียนที่อยู่ใหม่) ไปยังผู้เข้าร่วมทุกคน:

- `/hub/join <name>` — ส่งเมื่อผู้เข้าร่วมใหม่เข้าร่วมเซสชัน
- `/hub/leave <name>` — ส่งเมื่อผู้เข้าร่วมออกจากเซสชัน

```supercollider
OSCdef(\hubJoin,  { |msg| ("→ " ++ msg[1] ++ " เข้าร่วมแล้ว").postln }, '/hub/join');
OSCdef(\hubLeave, { |msg| ("← " ++ msg[1] ++ " ออกไปแล้ว").postln  }, '/hub/leave');
```

คุณยังสามารถใช้สภาพแวดล้อมที่ใช้งานร่วมกับ SC ได้ รหัสตั้งค่าที่เทียบเท่าสำหรับ Python (Supriya) และ Clojure (Overtone):

**Python (Supriya):**

```python
import threading
from pythonosc import dispatcher, osc_server
from pythonosc.udp_client import SimpleUDPClient

# เป้าหมาย: local Node.js bridge
bridge = SimpleUDPClient("127.0.0.1", 57121)

# รับข้อความ /remote/* และ relay คำสั่งต้นฉบับไปยัง scsynth
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

;; เป้าหมาย: local Node.js bridge
(def bridge (osc-client "127.0.0.1" 57121))

;; รับข้อความ /remote/* และ relay คำสั่งต้นฉบับไปยัง scsynth
(def receiver (osc-server 57120))
(osc-handle receiver "/remote/*"
  (fn [msg]
    (let [parts (clojure.string/split (:path msg) #"/")
          cmd (str "/" (clojure.string/join "/" (drop 3 parts)))]
      (apply snd cmd (:args msg)))))
```

#### 2. การตั้งค่า Local Bridge

```bash
cd bridge-local
npm install ws
node bridge.js
```

ตัวเลือก (ทั้งหมดเป็นทางเลือก แสดงค่าเริ่มต้น):

| ตัวเลือก | ค่าเริ่มต้น | คำอธิบาย |
|---------|------------|---------|
| `--sc-port` | 57120 | พอร์ตที่ SC/sclang รับ OSC |
| `--osc-port` | 57121 | พอร์ต UDP ในเครื่องที่ bridge รับฟัง OSC จาก SC |
| `--ws-port` | 8080 | พอร์ต WebSocket ที่ bridge เปิดเผยให้เบราว์เซอร์ |

#### ทางเลือก: Python CLI Bridge (local.py)

`local.py` แทนที่ทั้ง bridge.js และ index.html ในสคริปต์ Python เดียว ไม่ต้องใช้เบราว์เซอร์หรือ Node.js

```bash
pip install aioquic
python local.py your-hub-server.com --session my-session
```

ตัวเลือก:

| ตัวเลือก | ค่าเริ่มต้น | คำอธิบาย |
|---------|------------|---------|
| `server` | *(จำเป็น)* | ชื่อโฮสต์ของ hub server |
| `--port` | 8443 | พอร์ตของ hub server |
| `--sc-port` | 57120 | พอร์ตรับของ SC |
| `--osc-port` | 57121 | พอร์ตรับ OSC ในเครื่อง |
| `--session` | *(ถูกถาม)* | Session ID ที่ต้องการเข้าร่วม |
| `--name` | *(ทางเลือก)* | ชื่อที่แสดงของคุณ |
| `--insecure` | — | ปิดการตรวจสอบใบรับรอง TLS (สำหรับใบรับรองที่เซ็นเอง) |

เมื่อเชื่อมต่อแล้ว คอนโซลจะแสดงชื่อและ ID ที่ได้รับมอบหมาย การ routing OSC (datagram หรือ stream) ตามกฎเดียวกับ browser client หากการเชื่อมต่อขาดหาย bridge จะเชื่อมต่อใหม่โดยอัตโนมัติด้วย exponential backoff (1s → 30s)

> **หมายเหตุ:** เมื่อใช้ `local.py` ให้ส่ง OSC ไปยังพอร์ต 57121 (`--osc-port`) แทนการใช้เบราว์เซอร์ ตั้งค่า `~bridge = NetAddr("127.0.0.1", 57121)` ใน SC เหมือนกับ bridge.js

#### 3. การเชื่อมต่อเว็บ

เปิด URL ของ Web Client ในเบราว์เซอร์ที่รองรับ WebTransport ป้อน Session ID ชื่อที่แสดง (ทางเลือก ต้องไม่มี `/` หรือเกิน 64 ตัวอักษร) Hub Port (ค่าเริ่มต้น: `8443` ต้องตรงกับ `--port`) และ Bridge Port (ค่าเริ่มต้น: `8080` ต้องตรงกับ `--ws-port`) จากนั้นคลิก **Connect All** Client ID และชื่อที่แสดงจะปรากฏเมื่อเชื่อมต่อแล้ว หากการเชื่อมต่อล้มเหลว ไคลเอนต์จะเชื่อมต่อใหม่โดยอัตโนมัติด้วย exponential backoff (1s → 30s)

#### 4. การส่งข้อความ OSC

เมื่อผู้เข้าร่วมทุกคนเชื่อมต่อแล้ว ข้อความ OSC ที่ส่งไปยัง `~bridge` จะถูก relay ไปยัง scsynth instance ของผู้เข้าร่วมทุกคน ต่อไปนี้เป็นตัวอย่างพื้นฐานโดยใช้ sclang:

> **หมายเหตุ:** Node ID จะถูกแชร์กับผู้เข้าร่วมทุกคนในเซสชัน การใช้ ID เดียวกัน (เช่น `11000`) จากหลายผู้เข้าร่วมจะทำให้เกิดความขัดแย้ง — `/n_set` หรือ `/n_free` ของผู้เข้าร่วมคนหนึ่งจะส่งผลต่อ node ของอีกคน พิจารณาแบ่งช่วง ID ตามผู้เข้าร่วม (เช่น ดึงมาจาก client ID) ใช้ Group (`/g_new`) เพื่อแยก node ของผู้เข้าร่วมแต่ละคน หรือกำหนดผู้ส่งคนเดียวที่ควบคุม node ID ทั้งหมด

```supercollider
// เป้าหมาย: local Node.js bridge
~bridge = NetAddr("127.0.0.1", 57121);

// กำหนดและส่ง SynthDef
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

~bridge.sendMsg(\d_recv, ~def.asBytes);

// รอสักครู่ให้ผู้เข้าร่วมทุกคนโหลด SynthDef จากนั้น trigger โน้ต
~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);

// เปลี่ยนค่าพารามิเตอร์
~bridge.sendMsg(\n_set, 11000, \freq, 648);

// ปลดปล่อย node
~bridge.sendMsg(\n_free, 11000);
```

รหัสส่งที่เทียบเท่าสำหรับ Python (Supriya) และ Clojure (Overtone):

**Python (Supriya):**

```python
# กำหนด SynthDef และ compile เป็น bytes
@synthdef()
def sine_synth(freq=440, amp=0.2):
    sig = SinOsc.ar(frequency=freq) * amp
    Out.ar(bus=0, source=Pan2.ar(sig))

bridge.send_message("/d_recv", [sine_synth.compile()])

# รอสักครู่ให้ผู้เข้าร่วมทุกคนโหลด SynthDef จากนั้น trigger โน้ต
bridge.send_message("/s_new", ["sine-synth", 11000, 0, 1, "freq", 432])

# เปลี่ยนค่าพารามิเตอร์
bridge.send_message("/n_set", [11000, "freq", 648])

# ปลดปล่อย node
bridge.send_message("/n_free", [11000])
```

**Clojure (Overtone):**

```clojure
;; กำหนด SynthDef
(defsynth sine-synth [freq 440 amp 0.2]
  (out 0 (pan2 (* amp (sin-osc freq)))))

(osc-send bridge "/d_recv" (synthdef-bytes (:sdef sine-synth)))

;; รอสักครู่ให้ผู้เข้าร่วมทุกคนโหลด SynthDef จากนั้น trigger โน้ต
(osc-send bridge "/s_new" "sine-synth" 11000 0 1 "freq" 432)

;; เปลี่ยนค่าพารามิเตอร์
(osc-send bridge "/n_set" 11000 "freq" 648)

;; ปลดปล่อย node
(osc-send bridge "/n_free" 11000)
```

> **หมายเหตุ:** `synthdef-bytes` ให้มาโดย `overtone.sc.machinery.synthdef` และ serialize SynthDef ไปยังรูปแบบ binary ที่ scsynth คาดหวัง

## บันทึกทางเทคนิค

### การ Routing Traffic

ข้อความถูก route ไปยัง **WebTransport Stream** หาก:
- ข้อความเป็น **OSC Bundle** (ส่งผ่าน Stream เสมอเพื่อการส่ง timetag ที่เชื่อถือได้)
- ที่อยู่ OSC เริ่มต้นด้วย `/d_` (SynthDef), `/b_` (Buffer) หรือ `/sy` (Sync — สำหรับการส่งที่เชื่อถือได้ของการซิงโครไนซ์คำสั่ง async)
- ขนาดข้อมูลเกิน 1000 ไบต์

มิฉะนั้น **Datagram** จะถูกใช้เพื่อความหน่วงต่ำสุด

### การซิงโครไนซ์คำสั่ง Async

scsynth ประมวลผลคำสั่งหลายอย่างแบบ asynchronously — รวมถึง `/d_recv` (การโหลด SynthDef), `/b_alloc` (การจัดสรร buffer) และ `/b_gen` (การสร้าง buffer) `/sync` ง่ายๆ จากผู้ส่งยืนยันเพียงว่า **scsynth ของผู้ส่งเอง** ประมวลผล queue เสร็จแล้ว — ไม่ใช่ว่าผู้เข้าร่วม remote ทั้งหมดพร้อมแล้ว

`/sync` สามารถใช้กับคำสั่ง async ผสมใดก็ได้อย่างสม่ำเสมอ ตัวอย่างเช่น เพื่อให้แน่ใจว่าผู้เข้าร่วมทุกคนได้โหลด SynthDef และเติม buffer ก่อนเริ่มเล่น:

```supercollider
~bridge.sendMsg(\d_recv, ~def.asBytes);       // async: โหลด SynthDef
~bridge.sendMsg(\b_alloc, 0, 1024, 1);        // async: จัดสรร buffer (1024 เฟรม)
~bridge.sendMsg(\b_gen, 0, \sine1, 0, 1.0/1, 1.0/2, 1.0/3, 1.0/4, 1.0/5, 1.0/6);  // async: เติมด้วย additive sine partial
~bridge.sendMsg(\sync, 5678);                 // รอทั้งหมดข้างต้น
```

วิธีที่มีประสิทธิภาพมากขึ้นเป็นไปได้โดยใช้ `/who` และ client ID ขั้นตอนมีดังนี้:

1. ผู้เข้าร่วมแต่ละคนรันรหัสตั้งค่าด้านล่างก่อนเซสชันเริ่ม เมื่อ `/sync` มาถึง พวกเขาส่งต่อไปยัง scsynth ของตนเองและ broadcast `/synced` กลับผ่านฮับเมื่อ scsynth ของพวกเขายืนยันว่า queue เสร็จสมบูรณ์ ใช้ `thisProcess.addOSCRecvFunc` ที่นี่ด้วยเหตุผลเดียวกับ relay handler ทั่วไป — `OSCdef` ไม่สามารถกรองตาม port ได้อย่างน่าเชื่อถือ
2. ผู้ส่ง query `/who` เพื่อทราบจำนวนผู้เข้าร่วม จากนั้นส่งคำสั่ง async ตามด้วย `/sync`
3. ผู้ส่งนับการตอบกลับ `/synced` ที่เข้ามาและดำเนินการต่อเมื่อผู้เข้าร่วมทุกคนตอบกลับแล้ว

**การตั้งค่าผู้เข้าร่วม (รันก่อนเซสชัน, sclang):**

```supercollider
// เมื่อ /remote/*/sync มาจากฮับ ส่งต่อไปยัง local scsynth
// และ broadcast /synced กลับผ่านฮับเมื่อ queue เสร็จสมบูรณ์
OSCdef(\forwardSync, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    if((parts.size >= 3) && (parts[2] == 'sync'), {
        var syncId = msg[1];
        OSCdef(\waitAndReply, {|msg2|
            // scsynth ตอบกลับ: ['/done', '/sync', syncId]
            if((msg2[1] == '/sync') && (msg2[2] == syncId), {
                ~bridge.sendMsg('/synced', syncId);  // broadcast ผ่านฮับ
                OSCdef(\waitAndReply).free;
            });
        }, '/done');
        s.sendMsg('/sync', syncId);  // ส่งต่อไปยัง local scsynth
    });
}, nil);
```

**Workflow ผู้ส่ง (sclang):**

```supercollider
~bridge = NetAddr("127.0.0.1", 57121);
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

// ขั้นตอนที่ 1: query จำนวนผู้เข้าร่วม
OSCdef(\whoReply, {|msg|
    var count = msg.size - 1;  // msg[0] คือ '/who/reply' ที่เหลือคือชื่อผู้เข้าร่วม
    var received = 0;

    // ขั้นตอนที่ 3: นับการตอบกลับ /synced จากผู้เข้าร่วมทุกคน
    OSCdef(\collectSynced, {|msg2|
        received = received + 1;
        if(received >= count, {
            ~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);
            OSCdef(\collectSynced).free;
        });
    }, '/synced');

    // ขั้นตอนที่ 2: ส่งคำสั่ง async และ /sync
    ~bridge.sendMsg(\d_recv, ~def.asBytes);
    ~bridge.sendMsg(\sync, 1234);

    OSCdef(\whoReply).free;
}, '/who/reply');

~bridge.sendMsg('/who');
```

> **หมายเหตุ:** การตอบกลับ `/synced` จากผู้เข้าร่วมถูก broadcast ผ่านฮับและได้รับโดย `OSCdef(\collectSynced)` ของผู้ส่งบนพอร์ต 57120 `/synced` ของผู้ส่งเอง (จาก local scsynth ของพวกเขาผ่าน `\forwardSync`) ก็ถูกนับด้วย ดังนั้น `count` ควรสะท้อนถึงผู้เข้าร่วมทุกคนรวมถึงผู้ส่งหากพวกเขาก็รัน `\forwardSync` ด้วย

### การจัดการ Node และข้อความ FAILURE IN SERVER

เมื่อผู้เข้าร่วม remote ส่งคำสั่ง OSC เช่น `/s_new` หรือ `/n_free` หน้าต่าง Post ของ sclang อาจแสดงข้อความเช่น:

```
FAILURE IN SERVER /n_free Node 11000 not found
FAILURE IN SERVER /s_new duplicate node ID
```

สิ่งเหล่านี้ปรากฏเนื่องจาก sclang รักษาตารางการจัดการ node ภายในของตัวเอง ซึ่งได้รับการอัปเดตโดยข้อความตอบกลับ (เช่น `/n_end`) ที่ scsynth ส่งกลับไปยังไคลเอนต์ที่ออกคำสั่ง เมื่อคำสั่งมาถึงผ่านฮับจากผู้เข้าร่วม remote การตอบกลับของ scsynth จะไม่ถูก route กลับผ่านฮับไปยัง sclang ของผู้เข้าร่วมแต่ละคน — ดังนั้นตารางของ sclang จึงแตกต่างจากสถานะจริงของ scsynth

สิ่งสำคัญคือ **ข้อความเหล่านี้เพียงอย่างเดียวไม่ได้บ่งบอกว่า scsynth ประมวลผลคำสั่งอย่างถูกต้องหรือไม่** ข้อความ `FAILURE IN SERVER` อาจสะท้อนข้อผิดพลาดจริงบน scsynth (เช่น node ID ซ้ำที่เกิดจากผู้เข้าร่วมสองคนใช้ ID เดียวกัน) หรืออาจเป็นเพียงผลของตาราง sclang ที่ไม่ตรงกับสถานะจริงของ scsynth ข้อความไม่ได้แยกแยะทั้งสอง

เพื่อตรวจสอบสถานะจริงของ scsynth โดยตรง ให้ใช้:

```supercollider
s.queryAllNodes;
```

### การใช้ Buffer และการแชร์ Sample

สำหรับ wavetable หรือ buffer สร้างสั้นๆ (เช่น additive synthesis ผ่าน `/b_gen`) การส่ง `/b_alloc` และ `/b_gen` ผ่านฮับได้ผลดี — สิ่งเหล่านี้เกี่ยวข้องกับข้อมูลพารามิเตอร์จำนวนเล็กน้อยและเสร็จสิ้นอย่างรวดเร็วบน scsynth ของผู้เข้าร่วมแต่ละคน

สำหรับ sample เสียงที่บันทึกไว้ล่วงหน้า การถ่ายโอนข้อมูลเสียงจริงผ่านฮับไม่แนะนำ ไฟล์เสียงมักมีขนาดใหญ่ และการ route ผ่าน WebTransport จะทำให้เกิดความหน่วงอย่างมีนัยสำคัญและอาจทำให้การเชื่อมต่อรับภาระ แทนที่จะแจกจ่ายไฟล์ sample ให้กับผู้เข้าร่วมทุกคนก่อนเซสชัน (เช่น ผ่านการแชร์ไฟล์) และให้ผู้เข้าร่วมแต่ละคนโหลดในเครื่องโดยใช้ `/b_allocRead`:

```supercollider
// ผู้เข้าร่วมแต่ละคนโหลด sample ในเครื่อง — ไม่ส่งผ่านฮับ
s.sendMsg(\b_allocRead, 0, "/path/to/shared-sample.wav");
```

`/sync` ยังสามารถใช้เพื่อยืนยันว่าผู้เข้าร่วมทุกคนโหลดเสร็จแล้วก่อนที่การเล่นจะเริ่มต้น

### ใบรับรอง TLS

WebTransport ต้องการใบรับรอง TLS ที่ถูกต้อง สำหรับเซิร์ฟเวอร์สาธารณะ แนะนำ [Let's Encrypt](https://letsencrypt.org) โปรดทราบว่า **ใบรับรอง Cloudflare Origin CA ไม่สามารถใช้งานร่วมกับ WebTransport ได้ในปัจจุบัน** และจะทำให้เกิดข้อผิดพลาดในการเชื่อมต่อ สำหรับการพัฒนาในเครื่อง ให้เปิด Chrome ด้วย:

```
--origin-to-force-quic-on=yourdomain.com:8443
```

### ข้อกำหนด Firewall / พอร์ต

พอร์ตต่อไปนี้ต้องเปิดบน Hub server:

| พอร์ต | โปรโตคอล | วัตถุประสงค์ |
|------|---------|------------|
| 8443 (หรือกำหนดเอง) | **UDP** | WebTransport (QUIC/HTTP3) — พอร์ตหลักของ Hub เปลี่ยนได้ด้วย `--port` |
| 80 | TCP | Let's Encrypt HTTP-01 challenge (การออกและต่ออายุใบรับรอง) ไม่จำเป็นหากใช้ DNS-01 challenge หรือใบรับรองที่ออกแล้ว |
| 443 | TCP | HTTPS สำหรับ host `index.html` ไม่จำเป็นหาก host บนเซิร์ฟเวอร์แยกต่างหาก |

> **หมายเหตุ:** WebTransport ทำงานบน QUIC ซึ่งใช้ **UDP** — ไม่ใช่ TCP ตรวจสอบให้แน่ใจว่า firewall ของคุณอนุญาต UDP traffic บนพอร์ต Hub เนื่องจากสิ่งนี้มักถูกมองข้าม

## ใบอนุญาต

โปรเจกต์นี้ได้รับอนุญาตภายใต้ GNU GPL v3 — ดูไฟล์ [LICENSE](LICENSE) สำหรับรายละเอียด

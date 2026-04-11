# WebTransport OSC Hub

Sistem relay OSC dua arah, latensi rendah untuk SuperCollider menggunakan WebTransport (HTTP/3).

## Fitur

- **Infrastruktur Hybrid**: Merelay data melalui browser yang mendukung WebTransport, menggunakan Node.js bridge untuk mengintegrasikan lingkungan SuperCollider setiap peserta.
- **Python CLI Bridge**: `local.py` menyediakan koneksi yang sama seperti bridge.js + browser dalam satu skrip Python — tanpa browser.
- **Transmisi Hybrid**: Secara otomatis beralih antara Datagram (untuk data performa berkecepatan tinggi) dan Stream (untuk transfer SynthDef/Buffer yang andal).
- **Isolasi Session**: Mendukung beberapa session independen menggunakan Session ID.
- **Notifikasi Bergabung/Keluar**: Hub menyiarkan `/hub/join <name>` dan `/hub/leave <name>` ketika peserta masuk atau keluar dari session.
- **Mode Tanpa-Penulisan-Ulang**: Flag `--no-rewrite` meneruskan frame OSC apa adanya tanpa penulisan ulang alamat.

## Arsitektur Sistem

| Komponen | Deskripsi |
|---------|-----------|
| **Hub Server** (`wt_oschub.py`) | Server Python (aioquic) yang merelay OSC antar klien |
| **Python Bridge** (`local.py`) | Python CLI bridge — menghubungkan SC langsung ke Hub (tanpa browser) |
| **Web Client** (`index.html`) | Transport berbasis browser yang terhubung ke Hub |
| **Local Bridge** (`bridge.js`) | Node.js bridge yang menghubungkan SuperCollider (UDP) dan Web Client (WebSocket) |

## Demo

Hub demo publik tersedia di `connect.oschub.asia` (port `8443`). Perlu diperhatikan bahwa server ini mungkin tidak selalu dapat diakses.

- **Web Client**: Buka [https://connect.oschub.asia/](https://connect.oschub.asia/) di browser yang mendukung WebTransport
- **Python CLI Bridge**: `python local.py connect.oschub.asia --session your-session`

## Prasyarat

### Untuk Operator Hub
- Python 3.10+
- Server publik dengan IP/Domain tetap
- Sertifikat TLS yang valid (mis. Let's Encrypt)

### Untuk Peserta
- SuperCollider (lingkungan apa pun yang menggunakan scsynth sebagai audio engine)
- **Opsi A — Python CLI Bridge** (`local.py`): Python 3.10+ dan `pip install aioquic`
- **Opsi B — Browser + Node.js Bridge**: Node.js (untuk `bridge.js`) dan browser dengan dukungan WebTransport: Chrome 97+, Edge 98+, Firefox 115+, Opera 83+ (Safari belum didukung saat ini)

## Struktur Repository

```
.
├── server/
│   └── wt_oschub.py       # Hub relay server
├── bridge-local/
│   └── bridge.js          # Local UDP-WebSocket bridge (Opsi B)
├── client-web/
│   └── index.html         # Antarmuka web client (Opsi B)
├── local.py               # Python CLI bridge (Opsi A — tanpa browser)
├── .gitignore
├── LICENSE                # GNU GPL v3
└── README.md
```

## Setup & Eksekusi

### A. Untuk Operator Hub

Deploy `wt_oschub.py` di server publik:

```bash
cd server
pip install aioquic
python wt_oschub.py --cert /path/to/fullchain.pem --key /path/to/privkey.pem
```

Opsi tambahan (semua opsional):

| Opsi | Default | Deskripsi |
|------|---------|-----------|
| `--port` | 8443 | Port yang didengarkan hub |
| `--no-rewrite` | — | Nonaktifkan penulisan ulang alamat OSC (teruskan frame apa adanya) |
| `--max-msg-size` | 65536 | Ukuran pesan OSC maksimal dalam byte per pesan |
| `--rate-limit` | 200 | Pesan maksimal per detik per klien |
| `--log-level` | INFO | Tingkat log: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

Kemudian host `index.html` di web server yang mendukung HTTPS.

> **Catatan:** Port Hub default ke `8443` dan dapat diubah dengan `--port`. Web Client kini memiliki kolom input **Hub Port** (default: `8443`) — perbarui agar sesuai dengan `--port` jika diubah. Tidak perlu mengedit `index.html`. Hostname Hub server otomatis diturunkan dari `window.location.hostname` — tidak diperlukan entri URL manual selama Web server dan Hub server berjalan di mesin yang sama. Jika di mesin terpisah, edit `baseUrl` di `index.html` secara langsung.

Jika server menjalankan Linux, systemd dapat digunakan untuk mengelola `wt_oschub.py` sebagai layanan dan menjadwalkan restart harian. Buat dua file berikut:

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

Kemudian enable dan start keduanya:
```bash
systemctl daemon-reload
systemctl enable --now wt-oschub.service
systemctl enable --now wt-oschub.timer
```

> **Catatan:** Sesuaikan waktu `OnCalendar` dan path Python (`which python3`) dengan lingkungan Anda.

### B. Untuk Session Manager

Bagikan URL Web Client dan Session ID unik kepada semua peserta. ID Session tidak boleh melebihi 64 karakter.

### C. Untuk Peserta

#### 1. Setup SuperCollider

Unduh dan instal SuperCollider dari [supercollider.github.io](https://supercollider.github.io) jika belum ada. Luncurkan SuperCollider dan boot server.

Pesan yang direlay dari hub tiba dengan alamat OSC yang ditulis ulang menjadi `/remote/<sender_name>/<original_address>` (mis. `/remote/alice/s_new`). Ini memungkinkan penerima mengidentifikasi siapa yang mengirim setiap pesan dan menanganinya secara eksplisit melalui `OSCdef`.

Setup paling sederhana adalah `thisProcess.addOSCRecvFunc` yang menerima semua pesan remote, mengekstrak alamat asli, dan meneruskannya ke scsynth. `OSCdef` tidak dapat digunakan di sini karena mencocokkan alamat OSC secara tepat — `/remote` tidak akan cocok dengan `/remote/alice/s_new`. Simpan fungsi dalam variabel agar dapat dihapus nanti jika diperlukan.

Port penerima (`57120`) difilter secara eksplisit untuk menghindari konflik dengan aplikasi OSC lain yang berbagi instance sclang yang sama — misalnya SuperDirt mendaftarkan handler-nya sendiri dan dapat mengganggu jika tidak difilter. Port pengirim tidak difilter karena `local.py` menggunakan port UDP yang ditetapkan secara dinamis.

Pesan `/ping` ditangani oleh hub dan dikembalikan ke pengirim sebagai `/ping/reply` — tidak di-broadcast ke peserta lain. Handler relay berikut tidak perlu mengecualikan `/ping` secara eksplisit.

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

Untuk menghapus handler:

```supercollider
thisProcess.removeOSCRecvFunc(~remoteFunc);
```

Untuk menangani pesan dari pengirim atau perintah tertentu secara selektif, periksa `parts[1]` (nama pengirim) atau `cmd` di dalam handler:

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

> **Catatan:** OSC Bundle didukung sepenuhnya. Hub mem-parsing setiap Bundle secara rekursif, menulis ulang alamat setiap pesan yang terkandung menjadi `/remote/<sender_name>/<original_address>`, dan mempertahankan timetag. Ketika pengirim menggunakan `sendBundle(delta, ...)`, sclang di sisi penerima akan membongkar Bundle dan meneruskan timetag sebagai argumen `time`. Handler di atas sudah menangani ini melalui `time - thisThread.seconds` — tidak diperlukan pengaturan tambahan. Karena jam internal setiap peserta (`thisThread.seconds`) bersifat independen, beberapa drift tidak dapat dihindari. Menggunakan delta yang cukup besar (mis. 5 detik) membantu menyerap latensi jaringan dan perbedaan jam.

**Notifikasi sistem hub:** Hub mengirimkan dua pesan OSC berikut secara langsung (tanpa penulisan ulang alamat) kepada semua peserta:

- `/hub/join <name>` — dikirim ketika peserta baru bergabung ke session
- `/hub/leave <name>` — dikirim ketika peserta meninggalkan session

```supercollider
OSCdef(\hubJoin,  { |msg| ("→ " ++ msg[1] ++ " bergabung").postln }, '/hub/join');
OSCdef(\hubLeave, { |msg| ("← " ++ msg[1] ++ " keluar").postln  }, '/hub/leave');
```

Anda juga dapat menggunakan lingkungan kompatibel SC lainnya. Kode setup yang setara untuk Python (Supriya) dan Clojure (Overtone):

**Python (Supriya):**

```python
import threading
from pythonosc import dispatcher, osc_server
from pythonosc.udp_client import SimpleUDPClient

# Target: local Node.js bridge
bridge = SimpleUDPClient("127.0.0.1", 57121)

# Terima pesan /remote/* dan relay perintah asli ke scsynth
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

;; Target: local Node.js bridge
(def bridge (osc-client "127.0.0.1" 57121))

;; Terima pesan /remote/* dan relay perintah asli ke scsynth
(def receiver (osc-server 57120))
(osc-handle receiver "/remote/*"
  (fn [msg]
    (let [parts (clojure.string/split (:path msg) #"/")
          cmd (str "/" (clojure.string/join "/" (drop 3 parts)))]
      (apply snd cmd (:args msg)))))
```

#### 2. Setup Local Bridge

```bash
cd bridge-local
npm install ws
node bridge.js
```

Opsi (semua opsional, default ditampilkan):

| Opsi | Default | Deskripsi |
|------|---------|-----------|
| `--sc-port` | 57120 | Port tempat SC/sclang menerima OSC |
| `--osc-port` | 57121 | Port UDP lokal yang didengarkan bridge untuk OSC dari SC |
| `--ws-port` | 8080 | Port WebSocket yang diekspos bridge ke browser |

#### Alternatif: Python CLI Bridge (local.py)

`local.py` menggantikan bridge.js dan index.html sekaligus dalam satu skrip Python. Tidak diperlukan browser atau Node.js.

```bash
pip install aioquic
python local.py your-hub-server.com --session my-session
```

Opsi:

| Opsi | Default | Deskripsi |
|------|---------|-----------|
| `server` | *(wajib)* | Hostname hub server |
| `--port` | 8443 | Port hub server |
| `--sc-port` | 57120 | Port penerima SC |
| `--osc-port` | 57121 | Port penerima OSC lokal |
| `--session` | *(ditanya)* | ID session yang akan dimasuki |
| `--name` | *(opsional)* | Nama tampilan Anda |
| `--insecure` | — | Nonaktifkan verifikasi sertifikat TLS (untuk sertifikat self-signed) |

Setelah terhubung, konsol menampilkan nama dan ID yang ditetapkan. Routing OSC (datagram vs. stream) mengikuti aturan yang sama seperti browser client. Jika koneksi terputus, bridge akan terhubung kembali secara otomatis dengan exponential backoff (1 dtk → 30 dtk).

> **Catatan:** Saat menggunakan `local.py`, kirim OSC ke port 57121 (`--osc-port`) sebagai pengganti browser. Atur `~bridge = NetAddr("127.0.0.1", 57121)` di SC seperti halnya bridge.js.

#### 3. Koneksi Web

Buka URL Web Client di browser yang mendukung WebTransport. Masukkan Session ID (tidak boleh melebihi 64 karakter), opsional nama tampilan (tidak boleh mengandung `/` atau melebihi 64 karakter), Hub Port (default: `8443`, harus sesuai dengan `--port`), dan Bridge Port (default: `8080`, harus sesuai dengan `--ws-port`). Kemudian klik **Connect All**. Client ID dan nama tampilan akan ditampilkan setelah terhubung. Jika koneksi terputus, klien secara otomatis terhubung kembali dengan exponential backoff (1d → 30d).

#### 4. Mengirim Pesan OSC

Setelah semua peserta terhubung, pesan OSC yang dikirim ke `~bridge` akan direlay ke semua instans scsynth peserta. Berikut adalah contoh dasar menggunakan sclang:

> **Catatan:** Node ID dibagikan di semua peserta dalam satu session. Menggunakan ID yang sama (mis. `11000`) dari beberapa peserta akan menyebabkan konflik — `/n_set` atau `/n_free` satu peserta akan mempengaruhi node peserta lain. Pertimbangkan untuk mempartisi rentang ID per peserta (mis. diturunkan dari client ID), menggunakan Group (`/g_new`) untuk mengisolasi node setiap peserta, atau menunjuk satu pengirim yang mengelola semua node ID.

```supercollider
// Target: local Node.js bridge
~bridge = NetAddr("127.0.0.1", 57121);

// Definisikan dan kirim SynthDef
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

~bridge.sendMsg(\d_recv, ~def.asBytes);

// Tunggu sebentar agar semua peserta memuat SynthDef, lalu trigger nada
~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);

// Ubah nilai parameter
~bridge.sendMsg(\n_set, 11000, \freq, 648);

// Bebaskan node
~bridge.sendMsg(\n_free, 11000);
```

Kode pengiriman yang setara untuk Python (Supriya) dan Clojure (Overtone):

**Python (Supriya):**

```python
# Definisikan SynthDef dan compile ke bytes
@synthdef()
def sine_synth(freq=440, amp=0.2):
    sig = SinOsc.ar(frequency=freq) * amp
    Out.ar(bus=0, source=Pan2.ar(sig))

bridge.send_message("/d_recv", [sine_synth.compile()])

# Tunggu sebentar agar semua peserta memuat SynthDef, lalu trigger nada
bridge.send_message("/s_new", ["sine-synth", 11000, 0, 1, "freq", 432])

# Ubah nilai parameter
bridge.send_message("/n_set", [11000, "freq", 648])

# Bebaskan node
bridge.send_message("/n_free", [11000])
```

**Clojure (Overtone):**

```clojure
;; Definisikan SynthDef
(defsynth sine-synth [freq 440 amp 0.2]
  (out 0 (pan2 (* amp (sin-osc freq)))))

(osc-send bridge "/d_recv" (synthdef-bytes (:sdef sine-synth)))

;; Tunggu sebentar agar semua peserta memuat SynthDef, lalu trigger nada
(osc-send bridge "/s_new" "sine-synth" 11000 0 1 "freq" 432)

;; Ubah nilai parameter
(osc-send bridge "/n_set" 11000 "freq" 648)

;; Bebaskan node
(osc-send bridge "/n_free" 11000)
```

> **Catatan:** `synthdef-bytes` disediakan oleh `overtone.sc.machinery.synthdef` dan melakukan serialisasi SynthDef ke format binary yang diharapkan scsynth.

#### 5. Mengukur Latensi (/ping)

Peserta mana pun dapat mengukur latensi round-trip dengan mengirim pesan `/ping` beserta timestamp. Hub mengembalikannya sebagai `/ping/reply` dengan semua argumen dipertahankan. Perlu diketahui bahwa `local.py` mengirim keepalive `/ping` tanpa argumen setiap 20 detik — filter dengan memeriksa `msg.size > 1`:

```supercollider
// Ukur latensi secara terus-menerus dan perbarui ~latency setiap 2 detik
~pingTimes = Array.newClear(10);
~pingIndex = 0;

OSCdef(\pingReply, { |msg|
    if(msg.size > 1, {  // abaikan keepalive ping (tanpa argumen timestamp)
        var rtt = Date.getDate.rawSeconds - msg[1].asFloat;
        var latency = rtt / 2;
        ~pingTimes[~pingIndex % 10] = latency;
        ~pingIndex = ~pingIndex + 1;
        if(~pingIndex >= 10) {
            var valid = ~pingTimes.select({ |v| v.notNil });
            ~latency = valid.maxItem * 1.5;  // kasus terburuk × 1.5 margin keamanan
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

// Hentikan ping:
// ~pingRoutine.stop;
```

## Catatan Teknis

### Routing Traffic

Pesan dirutekan ke **WebTransport Stream** jika:
- Pesan adalah **OSC Bundle** (selalu dikirim melalui Stream untuk pengiriman timetag yang andal)
- Alamat OSC dimulai dengan `/d_` (SynthDef), `/b_` (Buffer), atau `/sy` (Sync — untuk pengiriman andal sinkronisasi perintah async)
- Ukuran data melebihi 1000 byte

Selain itu, **Datagram** digunakan untuk latensi minimum.

### Menyinkronkan Perintah Async

scsynth memproses banyak perintah secara asinkron — termasuk `/d_recv` (memuat SynthDef), `/b_alloc` (alokasi buffer), dan `/b_gen` (pembuatan buffer). `/sync` sederhana dari pengirim hanya mengkonfirmasi bahwa **scsynth pengirim sendiri** telah menyelesaikan pemrosesan antreannya — bukan bahwa semua peserta remote siap.

`/sync` dapat diterapkan secara merata ke kombinasi perintah async apa pun. Misalnya, untuk memastikan semua peserta telah memuat SynthDef dan mengisi buffer sebelum pemutaran:

```supercollider
~bridge.sendMsg(\d_recv, ~def.asBytes);       // async: muat SynthDef
~bridge.sendMsg(\b_alloc, 0, 1024, 1);        // async: alokasi buffer (1024 frame)
~bridge.sendMsg(\b_gen, 0, \sine1, 0, 1.0/1, 1.0/2, 1.0/3, 1.0/4, 1.0/5, 1.0/6);  // async: isi dengan parsial sinus aditif
~bridge.sendMsg(\sync, 5678);                 // tunggu semua hal di atas
```

Pendekatan yang lebih kuat dimungkinkan menggunakan `/who` dan client ID. Alurnya adalah sebagai berikut:

1. Setiap peserta menjalankan kode setup di bawah sebelum session dimulai. Ketika `/sync` tiba, mereka meneruskannya ke scsynth mereka sendiri dan menyiarkan `/synced` kembali melalui hub setelah scsynth mereka mengkonfirmasi antrean selesai. `thisProcess.addOSCRecvFunc` digunakan di sini karena alasan yang sama seperti handler relay umum — `OSCdef` tidak dapat memfilter berdasarkan port secara andal.
2. Pengirim mengquery `/who` untuk mengetahui jumlah peserta, kemudian mengirim perintah async diikuti `/sync`.
3. Pengirim menghitung balasan `/synced` yang masuk dan hanya melanjutkan ketika semua peserta telah merespons.

**Setup peserta (jalankan sebelum session, sclang):**

```supercollider
// Ketika /remote/*/sync tiba dari hub, teruskan ke local scsynth
// dan siarkan /synced kembali melalui hub setelah antrean selesai.
OSCdef(\forwardSync, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    if((parts.size >= 3) && (parts[2] == 'sync'), {
        var syncId = msg[1];
        OSCdef(\waitAndReply, {|msg2|
            // scsynth membalas: ['/done', '/sync', syncId]
            if((msg2[1] == '/sync') && (msg2[2] == syncId), {
                ~bridge.sendMsg('/synced', syncId);  // siaran melalui hub
                OSCdef(\waitAndReply).free;
            });
        }, '/done');
        s.sendMsg('/sync', syncId);  // teruskan ke local scsynth
    });
}, nil);
```

**Alur kerja pengirim (sclang):**

```supercollider
~bridge = NetAddr("127.0.0.1", 57121);
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

// Langkah 1: query jumlah peserta
OSCdef(\whoReply, {|msg|
    var count = msg.size - 1;  // msg[0] adalah '/who/reply', sisanya adalah nama peserta
    var received = 0;

    // Langkah 3: hitung balasan /synced dari semua peserta
    OSCdef(\collectSynced, {|msg2|
        received = received + 1;
        if(received >= count, {
            ~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);
            OSCdef(\collectSynced).free;
        });
    }, '/synced');

    // Langkah 2: kirim perintah async dan /sync
    ~bridge.sendMsg(\d_recv, ~def.asBytes);
    ~bridge.sendMsg(\sync, 1234);

    OSCdef(\whoReply).free;
}, '/who/reply');

~bridge.sendMsg('/who');
```

> **Catatan:** Balasan `/synced` dari peserta disiarkan melalui hub dan diterima oleh `OSCdef(\collectSynced)` pengirim di port 57120. `/synced` milik pengirim sendiri (dari local scsynth mereka melalui `\forwardSync`) juga dihitung, sehingga `count` harus mencerminkan semua peserta termasuk pengirim jika mereka juga menjalankan `\forwardSync`.

### Manajemen Node dan Pesan FAILURE IN SERVER

Ketika peserta remote mengirim perintah OSC seperti `/s_new` atau `/n_free`, jendela Post sclang mungkin menampilkan pesan seperti:

```
FAILURE IN SERVER /n_free Node 11000 not found
FAILURE IN SERVER /s_new duplicate node ID
```

Ini muncul karena sclang mempertahankan tabel manajemen node internalnya sendiri, yang diperbarui oleh pesan umpan balik (seperti `/n_end`) yang dikirim scsynth kembali ke klien yang mengeluarkan perintah. Ketika perintah tiba melalui hub dari peserta remote, umpan balik scsynth tidak diarahkan kembali melalui hub ke sclang setiap peserta — sehingga tabel sclang menyimpang dari keadaan scsynth yang sebenarnya.

Catatan penting adalah bahwa **pesan-pesan ini saja tidak menunjukkan apakah scsynth telah memproses perintah dengan benar atau tidak**. Pesan `FAILURE IN SERVER` mungkin mencerminkan kesalahan nyata pada scsynth (seperti node ID duplikat yang disebabkan oleh dua peserta menggunakan ID yang sama), atau mungkin hanya merupakan konsekuensi dari tabel sclang yang tidak tersinkronisasi dengan keadaan scsynth yang sebenarnya. Teks pesan tidak membedakan keduanya.

Untuk memeriksa keadaan scsynth yang sebenarnya secara langsung, gunakan:

```supercollider
s.queryAllNodes;
```

### Penggunaan Buffer dan Berbagi Sample

Untuk wavetable atau buffer generatif pendek (mis. sintesis aditif melalui `/b_gen`), mengirim `/b_alloc` dan `/b_gen` melalui hub bekerja dengan baik — ini hanya melibatkan jumlah kecil data parameter dan selesai dengan cepat di scsynth setiap peserta.

Untuk sample audio yang direkam sebelumnya, transfer data audio aktual melalui hub tidak direkomendasikan. File audio biasanya besar, dan merutekannya melalui WebTransport akan memperkenalkan latensi yang signifikan dan dapat membebani koneksi. Sebaliknya, distribusikan file sample ke semua peserta sebelum session (mis. melalui berbagi file) dan biarkan setiap peserta memuatnya secara lokal menggunakan `/b_allocRead`:

```supercollider
// Setiap peserta memuat sample secara lokal — tidak dikirim melalui hub
s.sendMsg(\b_allocRead, 0, "/path/to/shared-sample.wav");
```

`/sync` masih dapat digunakan untuk mengkonfirmasi bahwa semua peserta telah selesai memuat sebelum pemutaran dimulai.

### Sertifikat TLS

WebTransport memerlukan sertifikat TLS yang valid. Untuk server publik, [Let's Encrypt](https://letsencrypt.org) direkomendasikan. Perhatikan bahwa **sertifikat Cloudflare Origin CA saat ini tidak kompatibel** dengan WebTransport dan akan menyebabkan kesalahan koneksi. Untuk pengembangan lokal, luncurkan Chrome dengan:

```
--origin-to-force-quic-on=yourdomain.com:8443
```

### Persyaratan Firewall / Port

Port berikut harus terbuka di Hub server:

| Port | Protokol | Tujuan |
|------|---------|--------|
| 8443 (atau kustom) | **UDP** | WebTransport (QUIC/HTTP3) — port utama Hub. Ubah dengan `--port`. |
| 80 | TCP | Let's Encrypt HTTP-01 challenge (penerbitan dan pembaruan sertifikat). Tidak diperlukan jika menggunakan DNS-01 challenge atau sertifikat yang sudah diterbitkan. |
| 443 | TCP | HTTPS untuk hosting `index.html`. Tidak diperlukan jika dihosting di server terpisah. |

> **Catatan:** WebTransport berjalan di QUIC, yang menggunakan **UDP** — bukan TCP. Pastikan firewall Anda mengizinkan traffic UDP di port Hub, karena ini sering diabaikan.

## Lisensi

Proyek ini dilisensikan di bawah GNU GPL v3 — lihat file [LICENSE](LICENSE) untuk detailnya.

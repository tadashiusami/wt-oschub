# WebTransport OSC Hub

Isang mababa ang latency, bidirectional na sistema ng OSC relay para sa SuperCollider gamit ang WebTransport (HTTP/3).

## Mga Katangian

- **Hybrid na Imprastraktura**: Nagre-relay ng data sa pamamagitan ng browser na sumusuporta sa WebTransport, gamit ang Node.js bridge para isama ang SuperCollider environment ng bawat kalahok.
- **Hybrid na Transportasyon**: Awtomatikong nagpapalit sa pagitan ng Datagram (para sa mabilis na performance data) at Stream (para sa maaasahang paglipat ng SynthDef/Buffer).
- **Paghihiwalay ng Session**: Sinusuportahan ang maraming independyenteng session gamit ang mga Session ID.

## Arkitektura ng Sistema

| Bahagi | Paglalarawan |
|--------|-------------|
| **Hub Server** (`wt_oschub.py`) | Python server (aioquic) na nagre-relay ng OSC sa pagitan ng mga kliyente |
| **Web Client** (`index.html`) | Browser-based na transportasyon na kumokonekta sa Hub |
| **Local Bridge** (`bridge.js`) | Node.js bridge na nag-uugnay ng SuperCollider (UDP) at Web Client (WebSocket) |

## Mga Kinakailangan

### Para sa mga Operator ng Hub
- Python 3.10+
- Pampublikong server na may nakapirming IP/Domain
- Wastong TLS certificate (hal. Let's Encrypt)

### Para sa mga Kalahok
- SuperCollider (anumang kapaligiran na gumagamit ng scsynth bilang audio engine)
- Node.js (para sa pagpapatakbo ng lokal na bridge)
- Modernong web browser na may suporta sa WebTransport: Chrome 97+, Edge 98+, Firefox 115+, Opera 83+ (Hindi kasalukuyang sinusuportahan ng Safari)

## Istraktura ng Repository

```
.
├── server/
│   └── wt_oschub.py       # Hub relay server
├── bridge-local/
│   └── bridge.js          # Lokal na UDP-WebSocket bridge
├── client-web/
│   └── index.html         # Web client interface (HTML/JS)
├── .gitignore
├── LICENSE                # GNU GPL v3
└── README.md
```

## Setup at Pagpapatakbo

### A. Para sa Operator ng Hub

I-deploy ang `wt_oschub.py` sa isang pampublikong server:

```bash
cd server
pip install aioquic
python wt_oschub.py --cert /path/to/fullchain.pem --key /path/to/privkey.pem
```

Karagdagang mga opsyon (lahat ay opsyonal):

| Opsyon | Default | Paglalarawan |
|--------|---------|-------------|
| `--port` | 8443 | Port na pinakikinggan ng hub |
| `--max-msg-size` | 65536 | Max na laki ng OSC mensahe sa bytes bawat mensahe |
| `--rate-limit` | 200 | Max na mensahe bawat segundo bawat kliyente |
| `--log-level` | INFO | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

Pagkatapos ay i-host ang `index.html` sa HTTPS-enabled na web server.

> **Tandaan:** Ang port ng Hub ay default na `8443` at maaaring baguhin gamit ang `--port`. Ang Web Client ay mayroon na ngayong **Hub Port** na input field (default: `8443`) — i-update ito para tumugma sa `--port` kung binago. Hindi na kailangang i-edit ang `index.html`. Ang hostname ng Hub server ay awtomatikong kinukuha mula sa `window.location.hostname` — hindi kailangan ng manuwal na pagpasok ng URL hangga't ang Web server at Hub server ay nasa parehong makina. Kung nasa magkahiwalay na makina, i-edit ang `baseUrl` sa `index.html` nang direkta.

Kung ang server ay nagpapatakbo ng Linux, maaaring gamitin ang systemd para pamahalaan ang `wt_oschub.py` bilang isang serbisyo at mag-iskedyul ng araw-araw na pag-restart. Gumawa ng dalawang file na ito:

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

Pagkatapos ay i-enable at simulan ang pareho:
```bash
systemctl daemon-reload
systemctl enable --now wt-oschub.service
systemctl enable --now wt-oschub.timer
```

> **Tandaan:** I-adjust ang oras ng `OnCalendar` at ang Python path (`which python3`) para tumugma sa iyong kapaligiran.

### B. Para sa Session Manager

Ibahagi ang URL ng Web Client at isang natatanging Session ID sa lahat ng kalahok.

### C. Para sa mga Kalahok

#### 1. Setup ng SuperCollider

I-download at i-install ang SuperCollider mula sa [supercollider.github.io](https://supercollider.github.io) kung wala pa. Ilunsad ang SuperCollider at i-boot ang server.

Ang mga mensaheng na-relay mula sa hub ay darating na may OSC address na na-rewrite sa `/remote/<sender_name>/<original_address>` (hal. `/remote/alice/s_new`). Pinapahintulutan nito ang mga tatanggap na malaman kung sino ang nagpadala ng bawat mensahe at hawakan ito nang malinaw sa pamamagitan ng `OSCdef`.

Ang pinakasimpleng setup ay isang `OSCdef` na tumatanggap ng lahat ng remote na mensahe, kumukuha ng orihinal na address, at ipinapasa ang mga ito sa scsynth:

```supercollider
// Tumatanggap ng lahat ng remote OSC mensahe mula sa hub.
// Ang format ng address ay /remote/<sender_name>/<original_address>.
// Gamitin ang OSCFunc.trace para siyasatin ang mga papasok na mensahe sa panahon ng session.
OSCdef(\remoteAll, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    // parts = ['remote', 'alice', 's_new', ...]
    var cmd = ("/" ++ parts[2..].join("/")).asSymbol;
    s.sendMsg(cmd, *msg[1..]);
}, nil);
```

Para hawakan ang mga mensahe mula sa isang partikular na nagpadala o utos:

```supercollider
// Hawakan ang /s_new mula sa sinumang remote na kalahok
OSCdef(\remoteSNew, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    var senderName = parts[1];
    (senderName ++ " triggered /s_new").postln;
    s.sendMsg(\s_new, *msg[1..]);
}, nil);
```

> **Tandaan:** Ang mga OSC Bundle ay ganap na sinusuportahan. Ang hub ay nag-a-parse ng bawat Bundle nang recursive, isinusulat muli ang address ng bawat nakalamang mensahe sa `/remote/<sender_name>/<original_address>`, at pinapanatili ang timetag. Kapag ang isang nagpadala ay gumagamit ng `sendBundle(delta, ...)`, ang sclang sa receiving end ay i-unpack ang Bundle at ipapasa ang timetag bilang argument na `time` sa OSCdef handler. Para mapanatili ang nilayong timing at ipasa ito sa scsynth bilang Bundle, gamitin ang `time` tulad ng sumusunod:
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
> Dahil ang panloob na orasan ng bawat kalahok (`thisThread.seconds`) ay independyente, ang ilang drift ay hindi maiiwasan. Ang paggamit ng sapat na malaking delta (hal. 5 segundo) ay tumutulong na masipsip ang network latency at pagkakaiba ng orasan.

Maaari ka ring gumamit ng iba pang SC-compatible na kapaligiran. Katumbas na setup code para sa Python (supriya) at Clojure (Overtone):

**Python (supriya):**

```python
import threading
from pythonosc import dispatcher, osc_server
from pythonosc.udp_client import SimpleUDPClient

# Target: ang lokal na Node.js bridge
bridge = SimpleUDPClient("127.0.0.1", 57121)

# Tumatanggap ng /remote/* mensahe at irinerelay ang orihinal na utos sa scsynth
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

;; Target: ang lokal na Node.js bridge
(def bridge (osc-client "127.0.0.1" 57121))

;; Tumatanggap ng /remote/* mensahe at irinerelay ang orihinal na utos sa scsynth
(def receiver (osc-server 57120))
(osc-handle receiver "/remote/*"
  (fn [msg]
    (let [parts (clojure.string/split (:path msg) #"/")
          cmd (str "/" (clojure.string/join "/" (drop 3 parts)))]
      (apply snd cmd (:args msg)))))
```

#### 2. Setup ng Lokal na Bridge

```bash
cd bridge-local
npm install ws
node bridge.js
```

Mga opsyon (lahat ay opsyonal, mga default na value ay ipinapakita):

| Opsyon | Default | Paglalarawan |
|--------|---------|-------------|
| `--sc-port` | 57120 | Port kung saan tumatanggap ng OSC ang SC/sclang |
| `--osc-port` | 57121 | Lokal na UDP port na pinakikinggan ng bridge para sa OSC mula sa SC |
| `--ws-port` | 8080 | WebSocket port na inilalantad ng bridge sa browser |

#### 3. Koneksyon sa Web

Buksan ang URL ng Web Client sa isang browser na sumusuporta sa WebTransport. Ilagay ang Session ID, opsyonal ang display name (hindi dapat maglaman ng `/`), ang Hub Port (default: `8443`, dapat tumugma sa `--port`), at ang Bridge Port (default: `8080`, dapat tumugma sa `--ws-port`). Pagkatapos ay i-click ang **Connect All**. Ang iyong Client ID at display name ay ipapakita kapag nakakonekta na. Kung bumaba ang koneksyon, ang kliyente ay awtomatikong muling kokonekta na may exponential backoff (1s → 30s).

#### 4. Pagpapadala ng OSC Message

Kapag nakakonekta na ang lahat ng kalahok, ang mga OSC mensaheng ipinadala sa `~bridge` ay ire-relay sa lahat ng scsynth instance ng kalahok. Narito ang isang pangunahing halimbawa gamit ang sclang:

> **Tandaan:** Ang mga node ID ay ibinabahagi sa lahat ng kalahok sa isang session. Ang paggamit ng parehong ID (hal. `11000`) mula sa maraming kalahok ay magdudulot ng mga conflict — ang `/n_set` o `/n_free` ng isang kalahok ay makakaapekto sa node ng isa pa. Isaalang-alang ang pag-partition ng mga ID range bawat kalahok (hal. mula sa client ID), paggamit ng Groups (`/g_new`) para ihiwalay ang mga node ng bawat kalahok, o pagtatalaga ng isang nagpapadala na namamahala ng lahat ng node ID.

```supercollider
// Target: ang lokal na Node.js bridge
~bridge = NetAddr("127.0.0.1", 57121);

// Tukuyin at ipadala ang SynthDef
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

~bridge.sendMsg(\d_recv, ~def.asBytes);

// Maghintay ng sandali para ma-load ng lahat ng kalahok ang SynthDef, pagkatapos ay mag-trigger ng nota
~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);

// Baguhin ang halaga ng parameter
~bridge.sendMsg(\n_set, 11000, \freq, 648);

// I-free ang node
~bridge.sendMsg(\n_free, 11000);
```

Katumbas na sending code para sa Python (supriya) at Clojure (Overtone):

**Python (supriya):**

```python
# Tukuyin ang SynthDef at i-compile sa bytes
@synthdef()
def sine_synth(freq=440, amp=0.2):
    sig = SinOsc.ar(frequency=freq) * amp
    Out.ar(bus=0, source=Pan2.ar(sig))

bridge.send_message("/d_recv", [sine_synth.compile()])

# Maghintay ng sandali para ma-load ng lahat ng kalahok ang SynthDef, pagkatapos ay mag-trigger ng nota
bridge.send_message("/s_new", ["sine-synth", 11000, 0, 1, "freq", 432])

# Baguhin ang halaga ng parameter
bridge.send_message("/n_set", [11000, "freq", 648])

# I-free ang node
bridge.send_message("/n_free", [11000])
```

**Clojure (Overtone):**

```clojure
;; Tukuyin ang SynthDef
(defsynth sine-synth [freq 440 amp 0.2]
  (out 0 (pan2 (* amp (sin-osc freq)))))

(osc-send bridge "/d_recv" (synthdef-bytes (:sdef sine-synth)))

;; Maghintay ng sandali para ma-load ng lahat ng kalahok ang SynthDef, pagkatapos ay mag-trigger ng nota
(osc-send bridge "/s_new" "sine-synth" 11000 0 1 "freq" 432)

;; Baguhin ang halaga ng parameter
(osc-send bridge "/n_set" 11000 "freq" 648)

;; I-free ang node
(osc-send bridge "/n_free" 11000)
```

> **Tandaan:** Ang `synthdef-bytes` ay ibinibigay ng `overtone.sc.machinery.synthdef` at nagse-serialize ng SynthDef sa binary format na inaasahan ng scsynth.

## Mga Teknikal na Tala

### Routing ng Traffic

Ang mga mensahe ay niro-route sa **WebTransport Stream** kung:
- Ang mensahe ay isang **OSC Bundle** (palaging ipinapadala sa pamamagitan ng Stream para sa maaasahang paghahatid ng timetag)
- Ang OSC address ay nagsisimula sa `/d_` (SynthDef), `/b_` (Buffer), o `/sy` (Sync — para sa maaasahang paghahatid ng async command synchronization)
- Ang laki ng data ay lumalagpas sa 1000 bytes

Kung hindi, ang **Datagram** ay ginagamit para sa pinakamababang latency.

### Pag-synchronize ng Async Command

Ang scsynth ay nagpoproseso ng maraming utos nang asynchronously — kabilang ang `/d_recv` (pag-load ng SynthDef), `/b_alloc` (paglaan ng buffer), at `/b_gen` (pagbuo ng buffer). Ang simpleng `/sync` mula sa nagpadala ay nagkukumpirma lamang na ang **sariling scsynth ng nagpadala** ay natapos sa pagproseso ng queue nito — hindi na handa ang lahat ng remote na kalahok.

Ang `/sync` ay maaaring ilapat nang pantay sa anumang kombinasyon ng async na utos. Halimbawa, para matiyak na na-load ng lahat ng kalahok ang SynthDef at napunan ang buffer bago magsimula ang playback:

```supercollider
~bridge.sendMsg(\d_recv, ~def.asBytes);       // async: mag-load ng SynthDef
~bridge.sendMsg(\b_alloc, 0, 1024, 1);        // async: maglaan ng buffer (1024 frame)
~bridge.sendMsg(\b_gen, 0, \sine1, 0, 1.0/1, 1.0/2, 1.0/3, 1.0/4, 1.0/5, 1.0/6);  // async: punuin ng additive sine partial
~bridge.sendMsg(\sync, 5678);                 // hintayin ang lahat ng nasa itaas
```

Ang mas matibay na diskarte ay posible gamit ang `/who` at mga client ID. Ang proseso ay ganito:

1. Ang bawat kalahok ay nagpapatakbo ng setup code sa ibaba bago magsimula ang session. Kapag dumating ang `/sync`, ipinoproseso ito sa sarili nilang scsynth at bino-broadcast ang `/synced` pabalik sa pamamagitan ng hub kapag kinumpirma ng kanilang scsynth na kumpleto ang queue. Ginagamit ang `thisProcess.addOSCRecvFunc` dito sa parehong dahilan tulad ng pangkalahatang relay handler — hindi maaasahan ang `OSCdef` na mag-filter ayon sa port.
2. Ang nagpadala ay nagta-query ng `/who` para malaman ang bilang ng kalahok, pagkatapos ay nagpapadala ng mga async na utos na sinusundan ng `/sync`.
3. Ang nagpadala ay binibilang ang mga papasok na tugon ng `/synced` at nagpapatuloy lamang kapag sumagot ang lahat ng kalahok.

**Setup ng kalahok (patakbuhin bago magsimula ang session, sclang):**

```supercollider
// Kapag dumating ang /remote/*/sync mula sa hub, ipasa sa lokal na scsynth
// at i-broadcast ang /synced pabalik sa pamamagitan ng hub kapag kumpleto ang queue.
OSCdef(\forwardSync, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    if((parts.size >= 3) && (parts[2] == 'sync'), {
        var syncId = msg[1];
        OSCdef(\waitAndReply, {|msg2|
            // Tugon ng scsynth: ['/done', '/sync', syncId]
            if((msg2[1] == '/sync') && (msg2[2] == syncId), {
                ~bridge.sendMsg('/synced', syncId);  // i-broadcast sa pamamagitan ng hub
                OSCdef(\waitAndReply).free;
            });
        }, '/done');
        s.sendMsg('/sync', syncId);  // ipasa sa lokal na scsynth
    });
}, nil);
```

**Workflow ng nagpadala (sclang):**

```supercollider
~bridge = NetAddr("127.0.0.1", 57121);
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

// Hakbang 1: i-query ang bilang ng kalahok
OSCdef(\whoReply, {|msg|
    var count = msg.size - 1;  // ang msg[0] ay '/who/reply', ang natitira ay mga pangalan ng kalahok
    var received = 0;

    // Hakbang 3: bilangin ang mga tugon ng /synced mula sa lahat ng kalahok
    OSCdef(\collectSynced, {|msg2|
        received = received + 1;
        if(received >= count, {
            ~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);
            OSCdef(\collectSynced).free;
        });
    }, '/synced');

    // Hakbang 2: magpadala ng mga async na utos at /sync
    ~bridge.sendMsg(\d_recv, ~def.asBytes);
    ~bridge.sendMsg(\sync, 1234);

    OSCdef(\whoReply).free;
}, '/who/reply');

~bridge.sendMsg('/who');
```

> **Tandaan:** Ang mga tugon ng `/synced` mula sa mga kalahok ay bino-broadcast sa pamamagitan ng hub at tinatanggap ng `OSCdef(\collectSynced)` ng nagpadala sa port 57120. Ang sariling `/synced` ng nagpadala (mula sa kanilang lokal na scsynth sa pamamagitan ng `\forwardSync`) ay binibilang din, kaya ang `count` ay dapat sumalamin sa lahat ng kalahok kasama ang nagpadala kung sila rin ay nagpapatakbo ng `\forwardSync`.

### Pamamahala ng Node at Mga FAILURE IN SERVER Message

Kapag ang mga remote na kalahok ay nagpapadala ng mga OSC command tulad ng `/s_new` o `/n_free`, ang Post window ng sclang ay maaaring magpakita ng mga mensahe tulad ng:

```
FAILURE IN SERVER /n_free Node 11000 not found
FAILURE IN SERVER /s_new duplicate node ID
```

Lumilitaw ang mga ito dahil ang sclang ay nagpapanatili ng sarili nitong panloob na talahanayan ng pamamahala ng node, na ina-update ng mga feedback message (tulad ng `/n_end`) na ipinapadala ng scsynth pabalik sa kliyente na nag-isyu ng utos. Kapag ang mga utos ay dumating sa pamamagitan ng hub mula sa mga remote na kalahok, ang feedback ng scsynth ay hindi inire-route pabalik sa hub patungo sa sclang ng bawat kalahok — kaya ang talahanayan ng sclang ay lumalayo sa aktwal na estado ng scsynth.

Ang mahalagang caveat ay ang **mga mensaheng ito lamang ay hindi nagpapahiwatig kung na-process nang tama ng scsynth ang utos o hindi**. Ang isang `FAILURE IN SERVER` na mensahe ay maaaring sumasalamin sa isang tunay na error sa scsynth (tulad ng duplicate node ID na sanhi ng paggamit ng parehong ID ng dalawang kalahok), o maaaring simpleng resulta ng talahanayan ng sclang na hindi naka-sync sa aktwal na estado ng scsynth. Hindi naitatangi ng teksto ng mensahe ang dalawa.

Para suriin nang direkta ang aktwal na estado ng scsynth, gamitin ang:

```supercollider
s.queryAllNodes;
```

### Paggamit ng Buffer at Pagbabahagi ng Sample

Para sa wavetable o maikling generative na buffer (hal. additive synthesis sa pamamagitan ng `/b_gen`), ang pagpapadala ng `/b_alloc` at `/b_gen` sa pamamagitan ng hub ay gumagana nang mabuti — ang mga ito ay kinabibilangan lamang ng maliliit na dami ng parameter data at mabilis na nakukumpleto sa scsynth ng bawat kalahok.

Para sa mga pre-recorded na audio sample, ang paglipat ng aktwal na audio data sa pamamagitan ng hub ay hindi inirerekomenda. Ang mga audio file ay karaniwang malaki, at ang pag-route ng mga ito sa pamamagitan ng WebTransport ay magdudulot ng makabuluhang latency at maaaring mapahirapan ang koneksyon. Sa halip, ipamahagi ang mga sample file sa lahat ng kalahok bago magsimula ang session (hal. sa pamamagitan ng file sharing) at hayaan ang bawat kalahok na mag-load ng mga ito nang lokal gamit ang `/b_allocRead`:

```supercollider
// Ang bawat kalahok ay lokal na naglo-load ng sample — hindi ipinadala sa pamamagitan ng hub
s.sendMsg(\b_allocRead, 0, "/path/to/shared-sample.wav");
```

Ang `/sync` ay maaari pa ring gamitin para kumpirmahin na natapos ng lahat ng kalahok ang pag-load bago magsimula ang playback.

### Mga TLS Certificate

Ang WebTransport ay nangangailangan ng wastong TLS certificate. Para sa mga pampublikong server, inirerekomenda ang [Let's Encrypt](https://letsencrypt.org). Tandaan na ang **mga Cloudflare Origin CA certificate ay kasalukuyang hindi compatible** sa WebTransport at magdudulot ng mga error sa koneksyon. Para sa lokal na development, ilunsad ang Chrome gamit ang:

```
--origin-to-force-quic-on=yourdomain.com:8443
```

### Mga Kinakailangan sa Firewall / Port

Ang mga sumusunod na port ay dapat na bukas sa Hub server:

| Port | Protocol | Layunin |
|------|----------|---------|
| 8443 (o custom) | **UDP** | WebTransport (QUIC/HTTP3) — pangunahing port ng Hub. Baguhin gamit ang `--port`. |
| 80 | TCP | Let's Encrypt HTTP-01 challenge (pag-isyu at pag-renew ng certificate). Hindi kinakailangan kung gumagamit ng DNS-01 challenge o pre-issued na certificate. |
| 443 | TCP | HTTPS para sa pag-host ng `index.html`. Hindi kinakailangan kung naka-host sa isang hiwalay na server. |

> **Tandaan:** Ang WebTransport ay tumatakbo sa QUIC, na gumagamit ng **UDP** — hindi TCP. Tiyaking pinapayagan ng iyong firewall ang UDP traffic sa Hub port, dahil ito ay madalas na nakalimutan.

## Lisensya

Ang proyektong ito ay lisensyado sa ilalim ng GNU GPL v3 — tingnan ang file na [LICENSE](LICENSE) para sa mga detalye.

# WebTransport OSC Hub

WebTransport（HTTP/3）를 사용한 SuperCollider용 저지연 양방향 OSC 중계 시스템입니다.

## 특징

- **하이브리드 인프라**: WebTransport 지원 브라우저를 중계 클라이언트로 사용하고, Node.js 브리지로 각 참가자의 SuperCollider 환경과 연결합니다.
- **Python CLI 브리지**: `local.py`를 사용하면 브라우저 없이 bridge.js + 브라우저와 동일한 연결을 Python 스크립트 하나로 실현할 수 있습니다.
- **하이브리드 전송**: 연주 데이터에는 데이터그램（저지연）, SynthDef·Buffer 전송에는 스트림（신뢰성 우선）을 자동으로 구분하여 사용합니다.
- **세션 격리**: 세션 ID를 통해 여러 독립적인 세션을 동시에 운영할 수 있습니다.
- **입퇴장 알림**: 참가자의 입퇴장 시 허브가 `/hub/join <name>` 및 `/hub/leave <name>`을 브로드캐스트합니다.
- **노-리라이트 모드**: `--no-rewrite` 플래그를 사용하면 OSC 주소를 재작성하지 않고 프레임을 그대로 전달합니다.

## 시스템 아키텍처

| 컴포넌트 | 설명 |
|---------|------|
| **허브 서버**（`wt_oschub.py`） | 클라이언트 간 OSC를 중계하는 Python 서버（aioquic） |
| **Python 브리지**（`local.py`） | 브라우저 없이 SC를 허브에 직접 연결하는 Python CLI 브리지 |
| **웹 클라이언트**（`index.html`） | 허브에 연결하는 브라우저 기반 클라이언트 |
| **로컬 브리지**（`bridge.js`） | SuperCollider（UDP）와 웹 클라이언트（WebSocket）를 연결하는 Node.js 브리지 |

## 데모

공개 데모 Hub가 `connect.oschub.asia`（포트 `8443`）에서 이용 가능합니다. 이 서버는 항상 접속 가능하지 않을 수 있습니다.

- **웹 클라이언트**: WebTransport 지원 브라우저에서 [https://connect.oschub.asia/](https://connect.oschub.asia/) 열기
- **Python CLI 브리지**: `python local.py connect.oschub.asia --session your-session`

## 전제 조건

### 허브 운영자
- Python 3.10+
- 고정 IP 또는 도메인을 가진 공개 서버
- 유효한 TLS 인증서（예: Let's Encrypt）

### 참가자
- SuperCollider（scsynth를 오디오 엔진으로 사용하는 환경）
- **옵션 A — Python CLI 브리지**（`local.py`）: Python 3.10+ 및 `pip install aioquic`
- **옵션 B — 브라우저 + Node.js 브리지**: Node.js（`bridge.js` 실행용）와 WebTransport 지원 브라우저: Chrome 97+、Edge 98+、Firefox 115+、Opera 83+（Safari는 현재 미지원）

## 저장소 구성

```
.
├── server/
│   └── wt_oschub.py       # 허브 중계 서버
├── bridge-local/
│   └── bridge.js          # 로컬 UDP-WebSocket 브리지（옵션 B）
├── client-web/
│   └── index.html         # 웹 클라이언트（옵션 B）
├── local.py               # Python CLI 브리지（옵션 A — 브라우저 불필요）
├── .gitignore
├── LICENSE                # GNU GPL v3
└── README.md
```

## 설치 및 실행

### A. 허브 운영자

공개 서버에 `wt_oschub.py`를 배포합니다:

```bash
cd server
pip install aioquic
python wt_oschub.py --cert /path/to/fullchain.pem --key /path/to/privkey.pem
```

추가 옵션（모두 생략 가능）:

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--port` | 8443 | 허브 수신 포트 |
| `--no-rewrite` | — | OSC 주소 재작성 비활성화（프레임을 그대로 전달） |
| `--max-msg-size` | 65536 | 메시지당 최대 크기（바이트） |
| `--rate-limit` | 200 | 클라이언트당 최대 메시지 수／초 |
| `--log-level` | INFO | 로그 레벨: `DEBUG`、`INFO`、`WARNING`、`ERROR` |

이후 HTTPS를 지원하는 웹 서버에서 `index.html`을 호스팅합니다.

> **참고:** 허브 포트의 기본값은 `8443`이며 `--port`로 변경할 수 있습니다. 웹 클라이언트에는 **Hub Port** 입력 필드（기본값: `8443`）가 추가되었으므로, `--port`를 변경한 경우 해당 필드에서 맞춰 주세요. `index.html`을 직접 편집할 필요는 없습니다. 허브 서버의 호스트명은 `window.location.hostname`에서 자동으로 가져오므로, 웹 서버와 허브 서버가 같은 머신에서 동작하는 경우 URL을 수동으로 입력할 필요가 없습니다. 다른 머신에서 운영하는 경우 `index.html`의 `baseUrl`을 직접 편집하세요.

Linux 서버에서는 systemd를 사용하여 `wt_oschub.py`를 서비스로 관리하고 매일 자동 재시작할 수 있습니다. 다음 두 파일을 작성하세요:

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

두 파일을 활성화하고 시작:
```bash
systemctl daemon-reload
systemctl enable --now wt-oschub.service
systemctl enable --now wt-oschub.timer
```

> **참고:** `OnCalendar`의 시각과 Python 경로（`which python3`）는 환경에 맞게 조정하세요.

### B. 세션 관리자

웹 클라이언트의 URL과 고유한 세션 ID를 모든 참가자에게 공유합니다. 세션 ID는 64자를 초과하지 않아야 합니다.

### C. 참가자

#### 1. SuperCollider 설정

아직 설치하지 않았다면 [supercollider.github.io](https://supercollider.github.io)에서 다운로드·설치하고, SuperCollider를 실행하여 서버를 부팅합니다.

허브에서 중계된 메시지는 OSC 주소가 `/remote/<송신자명>/<원래 주소>`（예: `/remote/alice/s_new`）로 재작성되어 전달됩니다. 이를 통해 수신측은 누가 전송했는지 식별하고 `OSCdef`로 명시적으로 처리할 수 있습니다.

가장 간단한 설정은 `thisProcess.addOSCRecvFunc`로 모든 원격 메시지를 수신하고, 원래 주소를 추출하여 scsynth에 전달하는 것입니다. `OSCdef`는 여기서 사용할 수 없습니다. OSC 주소를 정확한 문자열로 매칭하기 때문에 `/remote`는 `/remote/alice/s_new`에 매칭되지 않습니다. 나중에 제거할 수 있도록 함수를 변수에 저장합니다.

수신 포트（`57120`）는 동일한 sclang 인스턴스를 공유하는 다른 OSC 애플리케이션과의 충돌을 피하기 위해 명시적으로 필터링됩니다. 예를 들어 SuperDirt는 자체 핸들러를 등록하며 필터링하지 않으면 간섭할 수 있습니다. 송신 포트는 필터링하지 않습니다. `local.py`는 동적으로 할당된 UDP 포트를 사용하기 때문입니다.

`/ping` 메시지는 허브가 처리하여 송신자에게 `/ping/reply`로 돌려줍니다 — 다른 참가자에게는 브로드캐스트되지 않습니다. 아래 릴레이 핸들러에서 `/ping`을 명시적으로 제외할 필요가 없습니다.

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

핸들러를 제거하려면:

```supercollider
thisProcess.removeOSCRecvFunc(~remoteFunc);
```

특정 송신자나 명령만 선택적으로 처리하려면, 핸들러 내에서 `parts[1]`（송신자명）또는 `cmd`를 확인합니다:

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

> **참고:** OSC Bundle은 완전히 지원됩니다. 허브는 번들을 중첩 포함하여 재귀적으로 분석하고, 포함된 각 메시지의 주소를 `/remote/<송신자명>/<원래 주소>`로 재작성하면서 timetag를 보존합니다. 송신측이 `sendBundle(delta, ...)`를 사용한 경우, 수신측 sclang은 번들을 분해하여 timetag를 `time` 인수로 전달합니다. 위의 핸들러는 이미 `time - thisThread.seconds`로 이를 처리하므로 추가 설정은 필요 없습니다. 각 참가자의 내부 클록（`thisThread.seconds`）은 독립적이므로 약간의 오차는 피할 수 없습니다. 충분히 큰 delta（예: 5초）를 사용하면 네트워크 지연과 클록 차이를 흡수할 수 있습니다.

**허브 시스템 알림:** 허브는 아래 두 가지 OSC 메시지를 주소 재작성 없이 모든 참가자에게 전송합니다:

- `/hub/join <name>` — 새 참가자가 세션에 입장했을 때
- `/hub/leave <name>` — 참가자가 세션에서 퇴장했을 때

```supercollider
OSCdef(\hubJoin,  { |msg| ("→ " ++ msg[1] ++ " 입장").postln }, '/hub/join');
OSCdef(\hubLeave, { |msg| ("← " ++ msg[1] ++ " 퇴장").postln  }, '/hub/leave');
```

다른 SC 호환 환경도 사용할 수 있습니다. Python（Supriya）과 Clojure（Overtone）의 동등한 설정 코드:

**Python (Supriya):**

```python
import threading
from pythonosc import dispatcher, osc_server
from pythonosc.udp_client import SimpleUDPClient

# 송신 대상: 로컬 Node.js 브리지
bridge = SimpleUDPClient("127.0.0.1", 57121)

# /remote/* 메시지를 수신하고 원래 명령을 scsynth에 중계합니다
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

;; 송신 대상: 로컬 Node.js 브리지
(def bridge (osc-client "127.0.0.1" 57121))

;; /remote/* 메시지를 수신하고 원래 명령을 scsynth에 중계합니다
(def receiver (osc-server 57120))
(osc-handle receiver "/remote/*"
  (fn [msg]
    (let [parts (clojure.string/split (:path msg) #"/")
          cmd (str "/" (clojure.string/join "/" (drop 3 parts)))]
      (apply snd cmd (:args msg)))))
```

#### 2. 로컬 브리지 설정

```bash
cd bridge-local
npm install ws
node bridge.js
```

옵션（모두 생략 가능, 기본값 표시）:

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--sc-port` | 57120 | SC/sclang이 OSC를 수신하는 포트 |
| `--osc-port` | 57121 | 브리지가 SC로부터 OSC를 받는 로컬 UDP 포트 |
| `--ws-port` | 8080 | 브리지가 브라우저에 노출하는 WebSocket 포트 |

#### 대안: Python CLI 브리지（local.py）

`local.py`는 bridge.js와 index.html 모두를 Python 스크립트 하나로 대체합니다. 브라우저나 Node.js가 필요 없습니다.

```bash
pip install aioquic
python local.py your-hub-server.com --session my-session
```

옵션:

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `server` | （필수） | 허브 서버 호스트명 |
| `--port` | 8443 | 허브 서버 포트 |
| `--sc-port` | 57120 | SC 수신 포트 |
| `--osc-port` | 57121 | 로컬 OSC 수신 포트 |
| `--session` | （프롬프트） | 참가할 세션 ID |
| `--name` | （선택사항） | 표시 이름 |
| `--insecure` | — | TLS 인증서 검증 비활성화（자가 서명 인증서용） |

연결이 완료되면 할당된 이름과 ID가 콘솔에 표시됩니다. OSC 라우팅（데이터그램 또는 스트림）은 브라우저 클라이언트와 동일한 규칙을 따릅니다. 연결이 끊어지면 지수 백오프（1초~30초）로 자동 재연결합니다.

> **참고:** `local.py`를 사용할 때는 브라우저 대신 포트 57121（`--osc-port`）로 OSC를 전송하세요. SC에서 `~bridge = NetAddr("127.0.0.1", 57121)`로 설정하면 됩니다（bridge.js와 동일）.

#### 3. 웹 연결

WebTransport 지원 브라우저에서 웹 클라이언트 URL을 열고, 세션 ID（64자 이하）·표시 이름（선택 사항, `/` 포함 불가, 64자 이하）·Hub Port（기본값: `8443`、`--port`에 맞게 조정）·Bridge Port（기본값: `8080`、`--ws-port`에 맞게 조정）를 입력하고 **Connect All**을 클릭합니다. 연결이 완료되면 클라이언트 ID와 표시 이름이 표시됩니다. 연결이 끊어지면 지수 백오프（1초~30초）로 자동 재연결합니다.

#### 4. OSC 메시지 전송

모든 참가자가 연결되면, `~bridge`에 전송한 OSC 메시지가 모든 참가자의 scsynth에 중계됩니다. sclang의 기본 사용 예:

> **참고:** 노드 ID는 세션 내 모든 참가자가 공유합니다. 여러 참가자가 같은 ID（예: `11000`）를 사용하면 충돌이 발생하여, 한 참가자의 `/n_set`이나 `/n_free`가 다른 참가자의 노드에 영향을 줄 수 있습니다. 참가자별로 ID 범위를 분할하거나（예: 클라이언트 ID에서 도출），Group（`/g_new`）으로 각 참가자의 노드를 격리하거나, 단일 송신자가 모든 노드 ID를 관리하는 방식을 고려하세요.

```supercollider
// 송신 대상: 로컬 Node.js 브리지
~bridge = NetAddr("127.0.0.1", 57121);

// SynthDef를 정의하고 전송합니다
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

~bridge.sendMsg(\d_recv, ~def.asBytes);

// 모든 참가자가 SynthDef를 로드한 후 소리를 냅니다
~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);

// 파라미터를 변경합니다
~bridge.sendMsg(\n_set, 11000, \freq, 648);

// 노드를 해제합니다
~bridge.sendMsg(\n_free, 11000);
```

Python（Supriya）과 Clojure（Overtone）의 동등한 전송 코드:

**Python (Supriya):**

```python
# SynthDef를 정의하고 바이트열로 컴파일합니다
@synthdef()
def sine_synth(freq=440, amp=0.2):
    sig = SinOsc.ar(frequency=freq) * amp
    Out.ar(bus=0, source=Pan2.ar(sig))

bridge.send_message("/d_recv", [sine_synth.compile()])

# 모든 참가자가 SynthDef를 로드한 후 소리를 냅니다
bridge.send_message("/s_new", ["sine-synth", 11000, 0, 1, "freq", 432])

# 파라미터를 변경합니다
bridge.send_message("/n_set", [11000, "freq", 648])

# 노드를 해제합니다
bridge.send_message("/n_free", [11000])
```

**Clojure (Overtone):**

```clojure
;; SynthDef를 정의합니다
(defsynth sine-synth [freq 440 amp 0.2]
  (out 0 (pan2 (* amp (sin-osc freq)))))

(osc-send bridge "/d_recv" (synthdef-bytes (:sdef sine-synth)))

;; 모든 참가자가 SynthDef를 로드한 후 소리를 냅니다
(osc-send bridge "/s_new" "sine-synth" 11000 0 1 "freq" 432)

;; 파라미터를 변경합니다
(osc-send bridge "/n_set" 11000 "freq" 648)

;; 노드를 해제합니다
(osc-send bridge "/n_free" 11000)
```

> **참고:** `synthdef-bytes`는 `overtone.sc.machinery.synthdef`가 제공하는 함수로, SynthDef를 scsynth가 요구하는 바이너리 형식으로 직렬화합니다.

#### 5. 레이턴시 측정（/ping）

타임스탬프가 포함된 `/ping` 메시지를 보내면 왕복 레이턴시를 측정할 수 있습니다. 허브는 모든 인수를 보존하여 `/ping/reply`로 돌려줍니다. `local.py`는 20초마다 인수 없는 `/ping` 키프얼라이브를 전송하므로, `msg.size > 1`로 필터링하세요:

```supercollider
// 2초마다 지연을 지속적으로 측정하여 ~latency 업데이트
~pingTimes = Array.newClear(10);
~pingIndex = 0;

OSCdef(\pingReply, { |msg|
    if(msg.size > 1, {  // 키프얼라이브 ping（타임스탬프 인수 없음）은 제외
        var rtt = Date.getDate.rawSeconds - msg[1].asFloat;
        var latency = rtt / 2;
        ~pingTimes[~pingIndex % 10] = latency;
        ~pingIndex = ~pingIndex + 1;
        if(~pingIndex >= 10) {
            var valid = ~pingTimes.select({ |v| v.notNil });
            ~latency = valid.maxItem * 1.5;  // 최악의 경우 × 1.5 안전 마진
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

// 정지하려면:
// ~pingRoutine.stop;
```

## 기술적 보충

### 트래픽 라우팅

다음 조건에 해당하는 메시지는 **WebTransport 스트림**으로 전송됩니다:
- **OSC Bundle**（timetag 신뢰성을 보장하기 위해 항상 스트림으로 전송）
- OSC 주소가 `/d_`（SynthDef）, `/b_`（Buffer）, `/sy`（Sync — 비동기 명령 동기화용）로 시작하는 경우
- 데이터 크기가 1000바이트를 초과하는 경우

그 외에는 최저 지연을 우선하여 **데이터그램**이 사용됩니다.

### 비동기 명령 동기화

scsynth의 많은 명령은 비동기로 처리됩니다（`/d_recv`에 의한 SynthDef 로드, `/b_alloc`에 의한 버퍼 확보, `/b_gen`에 의한 버퍼 생성 등）. 송신자 측에서의 단순한 `/sync`는 **송신자 자신의 scsynth** 큐가 완료되었음만 확인할 수 있고, 원격 참가자의 준비 완료는 보장하지 않습니다.

`/sync`는 임의의 비동기 명령 조합에 일괄 적용할 수 있습니다. 예를 들어 모든 참가자가 SynthDef 로드와 버퍼 채우기를 완료한 후 재생을 시작하려면:

```supercollider
~bridge.sendMsg(\d_recv, ~def.asBytes);       // 비동기: SynthDef 로드
~bridge.sendMsg(\b_alloc, 0, 1024, 1);        // 비동기: 버퍼 확보（1024 프레임）
~bridge.sendMsg(\b_gen, 0, \sine1, 0, 1.0/1, 1.0/2, 1.0/3, 1.0/4, 1.0/5, 1.0/6);  // 비동기: 가산 합성 사인파로 채우기
~bridge.sendMsg(\sync, 5678);                 // 위 모든 완료를 기다립니다
```

`/who`와 클라이언트 ID를 사용하면 보다 확실한 동기화가 가능합니다. 흐름은 다음과 같습니다:

1. 각 참가자는 세션 시작 전에 아래 설정 코드를 실행합니다. `/sync`가 도착하면 자신의 scsynth에 전달하고, scsynth가 큐 완료를 확인하면 허브를 통해 `/synced`를 브로드캐스트합니다. 포트 필터링이 `OSCdef`에서는 확실히 동작하지 않으므로, 여기서는 `thisProcess.addOSCRecvFunc`를 사용합니다.
2. 송신자는 `/who`로 참가자 수를 확인한 후, 비동기 명령과 `/sync`를 전송합니다.
3. 송신자는 수신한 `/synced` 응답을 세어 모든 참가자로부터 받으면 다음 단계로 진행합니다.

**참가자 설정（세션 시작 전에 실행, sclang）:**

```supercollider
// 허브에서 /remote/*/sync가 도착하면 로컬 scsynth에 전달하고,
// 큐가 완료되면 허브를 통해 /synced를 브로드캐스트합니다.
OSCdef(\forwardSync, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    if((parts.size >= 3) && (parts[2] == 'sync'), {
        var syncId = msg[1];
        OSCdef(\waitAndReply, {|msg2|
            // scsynth 응답: ['/done', '/sync', syncId]
            if((msg2[1] == '/sync') && (msg2[2] == syncId), {
                ~bridge.sendMsg('/synced', syncId);  // 허브를 통해 브로드캐스트
                OSCdef(\waitAndReply).free;
            });
        }, '/done');
        s.sendMsg('/sync', syncId);  // 로컬 scsynth에 전달
    });
}, nil);
```

**송신자 워크플로우（sclang）:**

```supercollider
~bridge = NetAddr("127.0.0.1", 57121);
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

// Step 1: 참가자 수를 가져옵니다
OSCdef(\whoReply, {|msg|
    var count = msg.size - 1;  // msg[0]은 '/who/reply', 나머지가 참가자 이름
    var received = 0;

    // Step 3: 모든 참가자의 /synced를 셉니다
    OSCdef(\collectSynced, {|msg2|
        received = received + 1;
        if(received >= count, {
            ~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);
            OSCdef(\collectSynced).free;
        });
    }, '/synced');

    // Step 2: 비동기 명령과 /sync를 전송합니다
    ~bridge.sendMsg(\d_recv, ~def.asBytes);
    ~bridge.sendMsg(\sync, 1234);

    OSCdef(\whoReply).free;
}, '/who/reply');

~bridge.sendMsg('/who');
```

> **참고:** 참가자로부터의 `/synced` 응답은 허브를 통해 브로드캐스트되며, 송신자의 `OSCdef(\collectSynced)`가 포트 57120에서 수신합니다. 송신자 자신의 `/synced`（`\forwardSync`를 통해 로컬 scsynth에서 도착하는 것）도 카운트에 포함되므로, 송신자도 `\forwardSync`를 실행하는 경우 `count`에 송신자 자신이 포함됩니다.

### 노드 관리와 FAILURE IN SERVER 메시지

원격 참가자가 `/s_new`나 `/n_free` 등의 OSC 명령을 전송하면, sclang의 포스트 윈도우에 다음과 같은 메시지가 표시될 수 있습니다:

```
FAILURE IN SERVER /n_free Node 11000 not found
FAILURE IN SERVER /s_new duplicate node ID
```

이는 sclang이 자체 내부 노드 관리 테이블을 갖고 있으며, scsynth가 명령을 발행한 클라이언트에 응답하는 피드백 메시지（`/n_end` 등）로 업데이트되는 구조이기 때문입니다. 허브를 통해 원격 참가자로부터 명령이 도착한 경우, scsynth의 피드백은 각 참가자의 sclang에 허브를 통해 반환되지 않으므로 sclang의 테이블이 scsynth의 실제 상태와 어긋납니다.

**중요한 점은, 이러한 메시지만으로는 scsynth가 명령을 올바르게 처리했는지 판단할 수 없다**는 것입니다. `FAILURE IN SERVER`는 두 참가자가 같은 ID를 사용한 중복 노드 ID와 같은 scsynth의 실제 오류를 나타내는 경우도, 단순히 sclang의 테이블이 scsynth의 실제 상태와 동기화되지 않은 경우도 있습니다. 메시지 텍스트만으로는 둘을 구별할 수 없습니다.

scsynth의 실제 상태를 직접 확인하려면:

```supercollider
s.queryAllNodes;
```

### 버퍼 사용과 샘플 공유

웨이브테이블이나 짧은 생성 버퍼（예: `/b_gen`에 의한 가산 합성）는 `/b_alloc`과 `/b_gen`을 허브를 통해 전송하는 것만으로 각 참가자의 scsynth에서 동작합니다. 파라미터 데이터만 포함하며 각 scsynth에서 신속하게 완료됩니다.

녹음된 오디오 샘플의 경우, 실제 오디오 데이터를 허브를 통해 전송하는 것은 권장하지 않습니다. 오디오 파일은 일반적으로 용량이 크고, WebTransport를 통해 전송하면 큰 지연이 발생하여 연결에 부담을 줄 수 있습니다. 대신 세션 전에 파일 공유 등으로 모든 참가자에게 샘플을 배포하고, 각자 로컬에서 `/b_allocRead`를 사용하여 로드하세요:

```supercollider
// 각 참가자가 샘플을 로컬에서 로드합니다 — 허브를 경유하지 않습니다
s.sendMsg(\b_allocRead, 0, "/path/to/shared-sample.wav");
```

재생 전에 모든 참가자의 로드가 완료되었는지 확인하기 위해 `/sync`를 사용할 수 있습니다.

### TLS 인증서

WebTransport에는 유효한 TLS 인증서가 필요합니다. 공개 서버에는 [Let's Encrypt](https://letsencrypt.org)를 권장합니다. **Cloudflare Origin CA 인증서는 현재 WebTransport와 호환되지 않으며**, 연결 오류의 원인이 됩니다. 로컬 개발 시에는 Chrome을 다음 옵션으로 실행하세요:

```
--origin-to-force-quic-on=yourdomain.com:8443
```

### 방화벽 / 포트 요건

허브 서버에서 다음 포트를 열어야 합니다:

| 포트 | 프로토콜 | 용도 |
|------|---------|------|
| 8443（또는 커스텀） | **UDP** | WebTransport（QUIC/HTTP3）— 허브의 메인 포트. `--port`로 변경 가능. |
| 80 | TCP | Let's Encrypt HTTP-01 챌린지（인증서 발급·갱신）. DNS-01 챌린지나 기발급 인증서를 사용하는 경우 불필요. |
| 443 | TCP | `index.html` 호스팅용 HTTPS. 별도 서버에서 호스팅하는 경우 불필요. |

> **참고:** WebTransport는 QUIC 위에서 동작하므로 사용하는 프로토콜은 **TCP가 아닌 UDP**입니다. 허브 포트에서 UDP 트래픽이 허용되어 있는지 확인하세요. 이 점은 쉽게 놓칠 수 있으므로 주의가 필요합니다.

## 라이선스

이 프로젝트는 GNU GPL v3 하에 공개되어 있습니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

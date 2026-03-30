# WebTransport OSC Hub

WebTransport（HTTP/3）を使用した、SuperCollider 向け低レイテンシー双方向 OSC 中継システムです。

## 特徴

- **ハイブリッドインフラ**: WebTransport 対応ブラウザを中継クライアントとして使用し、Node.js ブリッジで各参加者の SuperCollider 環境と接続します。
- **ハイブリッド転送**: 演奏データにはデータグラム（低レイテンシー）、SynthDef・Buffer 転送にはストリーム（信頼性重視）を自動的に使い分けます。
- **セッション隔離**: セッション ID による複数の独立したセッションを同時に運用できます。

## システムアーキテクチャ

| コンポーネント | 説明 |
|--------------|------|
| **ハブサーバー**（`wt_oschub.py`） | クライアント間で OSC を中継する Python サーバー（aioquic） |
| **ウェブクライアント**（`index.html`） | ハブに接続するブラウザベースのクライアント |
| **ローカルブリッジ**（`bridge.js`） | SuperCollider（UDP）とウェブクライアント（WebSocket）を接続する Node.js ブリッジ |

## 前提条件

### ハブ運営者向け
- Python 3.10+
- 固定 IP またはドメインを持つ公開サーバー
- 有効な TLS 証明書（例：Let's Encrypt）

### 参加者向け
- SuperCollider（scsynth をオーディオエンジンとして使用する環境）
- Node.js（ローカルブリッジ実行用）
- WebTransport 対応のモダンブラウザ: Chrome 97+、Edge 98+、Firefox 115+、Opera 83+（Safari は現在非対応）

## リポジトリ構成

```
.
├── server/
│   └── wt_oschub.py       # ハブ中継サーバー
├── bridge-local/
│   └── bridge.js          # ローカル UDP-WebSocket ブリッジ
├── client-web/
│   └── index.html         # ウェブクライアント（HTML/JS）
├── .gitignore
├── LICENSE                # GNU GPL v3
└── README.md
```

## セットアップと実行

### A. ハブ運営者向け

公開サーバーに `wt_oschub.py` をデプロイします:

```bash
cd server
pip install aioquic
python wt_oschub.py --cert /path/to/fullchain.pem --key /path/to/privkey.pem
```

次に、HTTPS 対応のウェブサーバーで `index.html` をホストします。

> **注意:** ハブのポートはデフォルトで `8443` です。`--port` で変更可能ですが、その場合は `index.html` 内のポート番号も合わせて変更してください。ハブサーバーのホスト名は `window.location.hostname` から自動取得されるため、ウェブサーバーとハブサーバーが同一マシンで動作している場合は URL の手動入力は不要です。別マシンの場合は `index.html` の `baseUrl` を直接編集してください。

Linux サーバーでは systemd を使って `wt_oschub.py` をサービスとして管理し、毎日自動再起動することができます。以下の2つのファイルを作成してください:

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

両方を有効化して起動:
```bash
systemctl daemon-reload
systemctl enable --now wt-oschub.service
systemctl enable --now wt-oschub.timer
```

> **注意:** `OnCalendar` の時刻と Python のパス（`which python3`）は環境に合わせて調整してください。

### B. セッション管理者向け

ウェブクライアントの URL と固有のセッション ID を全参加者に共有します。

### C. 参加者向け

#### 1. SuperCollider セットアップ

まだインストールしていない場合は [supercollider.github.io](https://supercollider.github.io) からダウンロード・インストールし、SuperCollider を起動してサーバーをブートします。

ハブから中継されたメッセージは、OSC アドレスが `/remote/<送信者名>/<元のアドレス>`（例：`/remote/alice/s_new`）に書き換えられて届きます。これにより、受信側は誰が送信したかを識別し、`OSCdef` で明示的に処理できます。

最もシンプルな設定は、全リモートメッセージを受信する単一の `OSCdef` で元のアドレスを取り出して scsynth へ転送するものです:

```supercollider
// ハブからの全リモート OSC メッセージを受信する。
// アドレスの形式は /remote/<送信者名>/<元のアドレス>。
// セッション中は OSCFunc.trace で受信メッセージを確認できます。
OSCdef(\remoteAll, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    // parts = ['remote', 'alice', 's_new', ...]
    var cmd = ("/" ++ parts[2..].join("/")).asSymbol;
    s.sendMsg(cmd, *msg[1..]);
}, nil);
```

特定の送信者やコマンドだけを処理する場合:

```supercollider
// 任意のリモート参加者からの /s_new を処理する
OSCdef(\remoteSNew, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    var senderName = parts[1];
    (senderName ++ " triggered /s_new").postln;
    s.sendMsg(\s_new, *msg[1..]);
}, nil);
```

> **注意:** OSC Bundle は完全に対応しています。ハブはバンドルをネストを含めて再帰的に解析し、含まれる各メッセージのアドレスを `/remote/<送信者名>/<元のアドレス>` に書き換えつつ、timetag を保持します。送信側が `sendBundle(delta, ...)` を使用した場合、受信側の sclang はバンドルを展開し、timetag を OSCdef ハンドラの `time` 引数として渡します。意図したタイミングを保持して scsynth へバンドルとして転送するには、以下のように `time` を使用します:
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
> 各参加者の内部クロック（`thisThread.seconds`）は独立しているため、多少のずれは避けられません。十分に大きな delta（例：5秒）を取ることで、ネットワーク遅延やクロック差を吸収できます。

他の SC 互換環境も使用できます。Python（supriya）と Clojure（Overtone）の同等のセットアップコード:

**Python (supriya):**

```python
import threading
from pythonosc import dispatcher, osc_server
from pythonosc.udp_client import SimpleUDPClient

# 送信先: ローカルの Node.js ブリッジ
bridge = SimpleUDPClient("127.0.0.1", 57121)

# /remote/* メッセージを受信し、元のコマンドを scsynth へ中継する
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

;; 送信先: ローカルの Node.js ブリッジ
(def bridge (osc-client "127.0.0.1" 57121))

;; /remote/* メッセージを受信し、元のコマンドを scsynth へ中継する
(def receiver (osc-server 57120))
(osc-handle receiver "/remote/*"
  (fn [msg]
    (let [parts (clojure.string/split (:path msg) #"/")
          cmd (str "/" (clojure.string/join "/" (drop 3 parts)))]
      (apply snd cmd (:args msg)))))
```

#### 2. ローカルブリッジのセットアップ

```bash
cd bridge-local
npm install ws
node bridge.js
```

オプション（すべて省略可能、デフォルト値を示す）:

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--sc-port` | 57120 | SC/sclang が OSC を受信するポート |
| `--osc-port` | 57121 | ブリッジが SC からの OSC を受け付けるローカル UDP ポート |
| `--ws-port` | 8080 | ブリッジがブラウザに公開する WebSocket ポート |

#### 3. ウェブ接続

WebTransport 対応ブラウザでウェブクライアントの URL を開き、セッション ID と表示名（任意）を入力して **Connect All** をクリックします。接続が完了するとクライアント ID と表示名が表示されます。接続が切断された場合は指数バックオフ（1秒〜30秒）で自動再接続します。

#### 4. OSC メッセージの送信

全参加者が接続したら、`~bridge` へ送信した OSC メッセージが全参加者の scsynth へ中継されます。sclang での基本的な使用例:

> **注意:** ノード ID はセッション内の全参加者で共有されます。複数の参加者が同じ ID（例：`11000`）を使用すると競合が発生し、一方の参加者の `/n_set` や `/n_free` が他の参加者のノードに影響を与えます。参加者ごとに ID 範囲を分割する（例：クライアント ID から導出）、Group（`/g_new`）で各参加者のノードを隔離する、または単一の送信者がすべてのノード ID を管理する方法を検討してください。

```supercollider
// 送信先: ローカルの Node.js ブリッジ
~bridge = NetAddr("127.0.0.1", 57121);

// SynthDef を定義して送信する
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

~bridge.sendMsg(\d_recv, ~def.asBytes);

// 全参加者が SynthDef を読み込む少し後に音を鳴らす
~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);

// パラメータを変更する
~bridge.sendMsg(\n_set, 11000, \freq, 648);

// ノードを解放する
~bridge.sendMsg(\n_free, 11000);
```

Python（supriya）と Clojure（Overtone）の同等の送信コード:

**Python (supriya):**

```python
# SynthDef を定義してバイト列にコンパイルする
@synthdef()
def sine_synth(freq=440, amp=0.2):
    sig = SinOsc.ar(frequency=freq) * amp
    Out.ar(bus=0, source=Pan2.ar(sig))

bridge.send_message("/d_recv", [sine_synth.compile()])

# 全参加者が SynthDef を読み込む少し後に音を鳴らす
bridge.send_message("/s_new", ["sine-synth", 11000, 0, 1, "freq", 432])

# パラメータを変更する
bridge.send_message("/n_set", [11000, "freq", 648])

# ノードを解放する
bridge.send_message("/n_free", [11000])
```

**Clojure (Overtone):**

```clojure
;; SynthDef を定義する
(defsynth sine-synth [freq 440 amp 0.2]
  (out 0 (pan2 (* amp (sin-osc freq)))))

(osc-send bridge "/d_recv" (synthdef-bytes (:sdef sine-synth)))

;; 全参加者が SynthDef を読み込む少し後に音を鳴らす
(osc-send bridge "/s_new" "sine-synth" 11000 0 1 "freq" 432)

;; パラメータを変更する
(osc-send bridge "/n_set" 11000 "freq" 648)

;; ノードを解放する
(osc-send bridge "/n_free" 11000)
```

> **注意:** `synthdef-bytes` は `overtone.sc.machinery.synthdef` が提供する関数で、SynthDef を scsynth が期待するバイナリ形式にシリアライズします。

## 技術的な補足

### トラフィックルーティング

以下の条件に当てはまるメッセージは **WebTransport ストリーム** で送信されます:
- OSC アドレスが `/d_`（SynthDef）、`/b_`（Buffer）、`/sy`（Sync — 非同期コマンド同期用）で始まる場合
- データサイズが 1000 バイトを超える場合

それ以外は最低レイテンシーを優先して **データグラム** が使用されます。

### 非同期コマンドの同期

scsynth の多くのコマンドは非同期で処理されます（`/d_recv` による SynthDef 読み込み、`/b_alloc` によるバッファ確保、`/b_gen` によるバッファ生成など）。送信者側での単純な `/sync` は、**送信者自身の scsynth** のキューが完了したことしか確認できず、リモート参加者の準備完了は保証しません。

`/sync` は任意の非同期コマンドの組み合わせに対して一様に適用できます。例えば、全参加者が SynthDef の読み込みとバッファの充填を完了してから再生を開始するには:

```supercollider
~bridge.sendMsg(\d_recv, ~def.asBytes);       // 非同期: SynthDef 読み込み
~bridge.sendMsg(\b_alloc, 0, 1024, 1);        // 非同期: バッファ確保（1024 フレーム）
~bridge.sendMsg(\b_gen, 0, \sine1, 0, 1.0/1, 1.0/2, 1.0/3, 1.0/4, 1.0/5, 1.0/6);  // 非同期: 加算合成正弦波で充填
~bridge.sendMsg(\sync, 5678);                 // 上記すべての完了を待つ
```

`/who` とクライアント ID を使うことで、より確実な同期が可能です。フローは以下の通りです:

1. 各参加者はセッション開始前に以下のセットアップコードを実行します。`/sync` が届いたら自分の scsynth へ転送し、scsynth がキューの完了を確認したらハブ経由で `/synced` をブロードキャストします。ポートによるフィルタリングが `OSCdef` では確実に動作しないため、ここでは `thisProcess.addOSCRecvFunc` を使用しています。
2. 送信者は `/who` で参加者数を取得してから、非同期コマンドと `/sync` を送信します。
3. 送信者は受信した `/synced` の返信を数え、全参加者から揃ったら次へ進みます。

**参加者セットアップ（セッション開始前に実行、sclang）:**

```supercollider
// ハブから /remote/*/sync が届いたらローカルの scsynth へ転送し、
// キューが完了したらハブ経由で /synced をブロードキャストする。
OSCdef(\forwardSync, {|msg|
    var parts = msg[0].asString.split($/).reject({|s| s.isEmpty});
    if((parts.size >= 3) && (parts[2] == 'sync'), {
        var syncId = msg[1];
        OSCdef(\waitAndReply, {|msg2|
            // scsynth の返信: ['/done', '/sync', syncId]
            if((msg2[1] == '/sync') && (msg2[2] == syncId), {
                ~bridge.sendMsg('/synced', syncId);  // ハブ経由でブロードキャスト
                OSCdef(\waitAndReply).free;
            });
        }, '/done');
        s.sendMsg('/sync', syncId);  // ローカルの scsynth へ転送
    });
}, nil);
```

**送信者のワークフロー（sclang）:**

```supercollider
~bridge = NetAddr("127.0.0.1", 57121);
~def = SynthDef(\sine, {|freq=440, amp=0.2|
    Out.ar(0, SinOsc.ar(freq, 0, amp).dup)
});

// Step 1: 参加者数を取得する
OSCdef(\whoReply, {|msg|
    var count = msg.size - 1;  // msg[0] は '/who/reply'、残りが参加者名
    var received = 0;

    // Step 3: 全参加者からの /synced を数える
    OSCdef(\collectSynced, {|msg2|
        received = received + 1;
        if(received >= count, {
            ~bridge.sendMsg(\s_new, \sine, 11000, 0, 1, \freq, 432);
            OSCdef(\collectSynced).free;
        });
    }, '/synced');

    // Step 2: 非同期コマンドと /sync を送信する
    ~bridge.sendMsg(\d_recv, ~def.asBytes);
    ~bridge.sendMsg(\sync, 1234);

    OSCdef(\whoReply).free;
}, '/who/reply');

~bridge.sendMsg('/who');
```

> **注意:** 参加者からの `/synced` 返信はハブ経由でブロードキャストされ、送信者の `OSCdef(\collectSynced)` がポート 57120 で受信します。送信者自身の `/synced`（`\forwardSync` 経由でローカルの scsynth から届くもの）もカウントに含まれるため、送信者も `\forwardSync` を実行している場合は `count` に送信者自身が含まれます。

### ノード管理と FAILURE IN SERVER メッセージ

リモート参加者が `/s_new` や `/n_free` などの OSC コマンドを送信すると、sclang のポストウィンドウに以下のようなメッセージが表示されることがあります:

```
FAILURE IN SERVER /n_free Node 11000 not found
FAILURE IN SERVER /s_new duplicate node ID
```

これは、sclang が独自の内部ノード管理テーブルを持っており、scsynth がコマンドを発行したクライアントへ返信するフィードバックメッセージ（`/n_end` など）によって更新される仕組みになっているためです。ハブ経由でリモート参加者からコマンドが届いた場合、scsynth のフィードバックは各参加者の sclang へはハブ経由で返されないため、sclang のテーブルが scsynth の実際の状態と乖離します。

**重要な点は、これらのメッセージだけでは scsynth がコマンドを正しく処理したかどうかを判断できない**ということです。`FAILURE IN SERVER` は、2人の参加者が同じ ID を使用したことによる重複ノード ID のような scsynth での実際のエラーを示している場合も、単に sclang のテーブルが scsynth の実際の状態と同期していないだけの場合もあります。メッセージのテキストだけでは両者を区別できません。

scsynth の実際の状態を直接確認するには:

```supercollider
s.queryAllNodes;
```

### バッファの使用とサンプル共有

ウェーブテーブルや短い生成バッファ（例：`/b_gen` による加算合成）は、`/b_alloc` と `/b_gen` をハブ経由で送信するだけで各参加者の scsynth で動作します。パラメータデータのみを含み、各 scsynth で迅速に完了します。

録音済みオーディオサンプルについては、実際のオーディオデータをハブ経由で転送することは推奨しません。オーディオファイルは一般的に大容量であり、WebTransport 経由で送信すると大きな遅延が発生し、接続に負担をかける可能性があります。代わりに、セッション前にファイル共有などで全参加者にサンプルを配布し、各自がローカルで `/b_allocRead` を使って読み込んでください:

```supercollider
// 各参加者がサンプルをローカルで読み込む — ハブは経由しない
s.sendMsg(\b_allocRead, 0, "/path/to/shared-sample.wav");
```

再生前に全参加者の読み込みが完了したことを確認するために `/sync` を使用できます。

### TLS 証明書

WebTransport には有効な TLS 証明書が必要です。公開サーバーには [Let's Encrypt](https://letsencrypt.org) を推奨します。**Cloudflare Origin CA 証明書は現在 WebTransport と互換性がなく**、接続エラーの原因となります。ローカル開発時は Chrome を以下のオプションで起動してください:

```
--origin-to-force-quic-on=yourdomain.com:8443
```

### ファイアウォール / ポート要件

ハブサーバーで以下のポートを開放する必要があります:

| ポート | プロトコル | 用途 |
|--------|-----------|------|
| 8443（またはカスタム） | **UDP** | WebTransport（QUIC/HTTP3）— ハブのメインポート。`--port` で変更可能。 |
| 80 | TCP | Let's Encrypt HTTP-01 チャレンジ（証明書の発行・更新）。DNS-01 チャレンジや発行済み証明書を使用する場合は不要。 |
| 443 | TCP | `index.html` のホスティング用 HTTPS。別サーバーでホストする場合は不要。 |

> **注意:** WebTransport は QUIC 上で動作するため、使用するプロトコルは **TCP ではなく UDP** です。ハブのポートで UDP トラフィックが許可されていることを確認してください。この点は見落とされやすいので注意が必要です。

## ライセンス

このプロジェクトは GNU GPL v3 のもとで公開されています。詳細は [LICENSE](LICENSE) ファイルを参照してください。

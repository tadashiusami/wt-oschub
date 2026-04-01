"""
local.py
Local UDP<->WebTransport bridge for wt-oschub.
Forwards raw OSC between SuperCollider and the WebTransport hub server.

Usage:
    python local.py <server> [--port PORT] [--sc-port PORT] [--osc-port PORT]
                              [--session SESSION] [--name NAME] [--insecure]
"""

import asyncio
import socket
import ssl
import argparse
import threading
from urllib.parse import urlencode

from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import DatagramReceived, HeadersReceived, WebTransportStreamDataReceived
from aioquic.quic.configuration import QuicConfiguration

# --- Arguments ---
parser = argparse.ArgumentParser(description="SC <-> WebTransport bridge for wt-oschub")
parser.add_argument("server", help="Hub server hostname (e.g. your-server.com)")
parser.add_argument("--port",     type=int, default=8443,  help="Hub server port (default: 8443)")
parser.add_argument("--sc-port",  type=int, default=57120, help="SC receive port (default: 57120)")
parser.add_argument("--osc-port", type=int, default=57121, help="Local OSC receive port (default: 57121)")
parser.add_argument("--session",  default=None, help="Session ID (prompted if omitted)")
parser.add_argument("--name",     default=None, help="Your display name (optional)")
parser.add_argument("--insecure", action="store_true",
                    help="Disable TLS certificate verification (for self-signed certs)")
args = parser.parse_args()

MY_SESSION = args.session if args.session else input("Session ID: ").strip()
SC_RECEIVE_PORT = args.sc_port
LOCAL_OSC_PORT  = args.osc_port

RECONNECT_DELAY_INIT = 1
RECONNECT_DELAY_MAX  = 30
MAX_STREAM_BUFFER    = 65536  # bytes; mirrors server-side max_msg_size default

sc_send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


# --- OSC / QUIC helpers ---

def encode_varint(value: int) -> bytes:
    """Encode an integer as a QUIC variable-length integer."""
    if value <= 63:         return bytes([value])
    elif value <= 16383:    return ((value | 0x4000).to_bytes(2, 'big'))
    elif value <= 1073741823: return ((value | 0x80000000).to_bytes(4, 'big'))
    else:                   return ((value | 0xC000000000000000).to_bytes(8, 'big'))


def parse_osc_address(data: bytes) -> str:
    """Extract the OSC address string from a raw OSC message."""
    if not data or data[0:1] != b'/':
        return ''
    try:
        return data[:data.index(b'\x00')].decode('utf-8')
    except Exception:
        return ''


def decode_varint(data: bytes, pos: int = 0):
    """Decode a QUIC variable-length integer at pos. Returns (value, new_pos)."""
    if pos >= len(data):
        raise ValueError("Buffer too short")
    first = data[pos]
    prefix = (first & 0xC0) >> 6
    if prefix == 0:
        return first & 0x3F, pos + 1
    elif prefix == 1:
        if pos + 2 > len(data): raise ValueError("Buffer too short")
        return int.from_bytes(data[pos:pos+2], 'big') & 0x3FFF, pos + 2
    elif prefix == 2:
        if pos + 4 > len(data): raise ValueError("Buffer too short")
        return int.from_bytes(data[pos:pos+4], 'big') & 0x3FFFFFFF, pos + 4
    else:
        if pos + 8 > len(data): raise ValueError("Buffer too short")
        return int.from_bytes(data[pos:pos+8], 'big') & 0x3FFFFFFFFFFFFFFF, pos + 8


def parse_osc_strings(data: bytes) -> list:
    """Extract all null-terminated, 4-byte-aligned strings from an OSC message."""
    results, pos = [], 0
    while pos < len(data):
        try:
            end = data.index(b'\x00', pos)
            results.append(data[pos:end].decode('utf-8'))
            pos = (end + 4) & ~3  # advance past null + padding
        except (ValueError, UnicodeDecodeError):
            break
    return results


# --- WebTransport protocol ---

class WTBridgeProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._http = H3Connection(self._quic, enable_webtransport=True)
        self._session_stream_id = None
        self._ready = asyncio.Event()
        self._recv_queue: asyncio.Queue = asyncio.Queue()
        self._stream_buffers: dict = {}

    def quic_event_received(self, event):
        if self._http is None:
            return
        for http_event in self._http.handle_event(event):
            if isinstance(http_event, HeadersReceived):
                headers = dict(http_event.headers)
                status = headers.get(b':status', b'')
                if status == b'200':
                    self._session_stream_id = http_event.stream_id
                    self._ready.set()
                else:
                    print(f"[error] Hub rejected connection: HTTP {status.decode()}", flush=True)

            elif isinstance(http_event, DatagramReceived):
                self._recv_queue.put_nowait(http_event.data)

            elif isinstance(http_event, WebTransportStreamDataReceived):
                sid = http_event.stream_id
                buf = self._stream_buffers.get(sid, b'') + http_event.data
                if len(buf) > MAX_STREAM_BUFFER:
                    self._stream_buffers.pop(sid, None)
                    continue
                if not http_event.stream_ended:
                    self._stream_buffers[sid] = buf
                    continue
                self._stream_buffers.pop(sid, None)
                # Strip WebTransport stream header (stream-type varint + session-id varint)
                try:
                    _, p = decode_varint(buf, 0)
                    _, p = decode_varint(buf, p)
                    buf = buf[p:]
                except Exception:
                    start = next((i for i, b in enumerate(buf) if b in (0x2F, 0x23)), 0)
                    buf = buf[start:]
                self._recv_queue.put_nowait(buf)

    def establish_session(self, authority: str, path: str):
        """Send HTTP CONNECT to establish a WebTransport session."""
        stream_id = self._quic.get_next_available_stream_id(is_unidirectional=False)
        self._http.send_headers(
            stream_id=stream_id,
            headers=[
                (b':method',   b'CONNECT'),
                (b':scheme',   b'https'),
                (b':authority', authority.encode()),
                (b':path',     path.encode()),
                (b':protocol', b'webtransport'),
            ]
        )
        self.transmit()

    def send_datagram(self, data: bytes):
        if self._session_stream_id is None:
            return
        self._http.send_datagram(self._session_stream_id, data)
        self.transmit()

    def send_stream(self, data: bytes):
        if self._session_stream_id is None:
            return
        stream_id = self._quic.get_next_available_stream_id(is_unidirectional=True)
        header = encode_varint(0x54) + encode_varint(self._session_stream_id)
        self._quic.send_stream_data(stream_id=stream_id, data=header + data, end_stream=True)
        self.transmit()

    def send_osc(self, data: bytes):
        """Route OSC to datagram or stream, mirroring the browser client's logic."""
        if data[0:1] == b'#':  # OSC bundle — always use reliable stream
            self.send_stream(data)
            return
        address = parse_osc_address(data)
        if address.startswith(('/d_', '/b_', '/sy')) or len(data) > 1000:
            self.send_stream(data)
        else:
            self.send_datagram(data)


# --- UDP receiver thread: SC -> hub ---

def udp_receiver(proto_ref: list, loop_ref: list):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("127.0.0.1", LOCAL_OSC_PORT))
    except OSError as e:
        print(f"[error] Cannot bind UDP port {LOCAL_OSC_PORT}: {e}", flush=True)
        return
    print(f"OSC listening on port {LOCAL_OSC_PORT}")
    while True:
        try:
            data, _ = sock.recvfrom(65536)
        except OSError as e:
            print(f"[error] UDP receive error: {e}", flush=True)
            break
        proto = proto_ref[0]
        loop  = loop_ref[0]
        if proto is not None and loop is not None:
            loop.call_soon_threadsafe(proto.send_osc, data)


# --- Main ---

async def run():
    proto_ref = [None]
    loop_ref  = [asyncio.get_running_loop()]

    t = threading.Thread(target=udp_receiver, args=(proto_ref, loop_ref), daemon=True)
    t.start()

    qs = urlencode({'id': MY_SESSION, **({'name': args.name} if args.name else {})})
    path      = f'/join?{qs}'
    authority = f'{args.server}:{args.port}'

    configuration = QuicConfiguration(
        is_client=True,
        alpn_protocols=H3_ALPN,
        max_datagram_frame_size=1500,
    )
    if args.insecure:
        configuration.verify_mode = ssl.CERT_NONE

    reconnect_delay = RECONNECT_DELAY_INIT

    while True:
        try:
            print(f"Connecting to {authority} (session: {MY_SESSION})...")
            async with connect(
                args.server, args.port,
                configuration=configuration,
                create_protocol=WTBridgeProtocol,
            ) as protocol:
                proto_ref[0] = protocol
                reconnect_delay = RECONNECT_DELAY_INIT

                protocol.establish_session(authority, path)
                try:
                    await asyncio.wait_for(protocol._ready.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    print("[error] Timed out waiting for WebTransport session", flush=True)
                    proto_ref[0] = None
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, RECONNECT_DELAY_MAX)
                    continue

                # Forward received OSC to SC
                while True:
                    data = await protocol._recv_queue.get()
                    address = parse_osc_address(data)

                    if address == '/welcome':
                        parts = parse_osc_strings(data)
                        # ['/welcome', ',ss', client_id, display_name]
                        cid  = parts[2] if len(parts) > 2 else '?'
                        name = parts[3] if len(parts) > 3 else cid
                        print(f"Joined as '{name}' (ID: {cid})")
                        continue

                    if address in ('/hub/join', '/hub/leave'):
                        parts = parse_osc_strings(data)
                        who    = parts[2] if len(parts) > 2 else '?'
                        action = 'joined' if address == '/hub/join' else 'left'
                        print(f"[info] {who} {action}")
                        # fall through to forward to SC

                    try:
                        sc_send_sock.sendto(data, ("127.0.0.1", SC_RECEIVE_PORT))
                    except OSError as e:
                        print(f"[error] UDP send to SC failed: {e}", flush=True)

        except KeyboardInterrupt:
            print("Shutting down...")
            break
        except Exception as e:
            proto_ref[0] = None
            print(f"Disconnected: {e}. Reconnecting in {reconnect_delay}s...", flush=True)
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, RECONNECT_DELAY_MAX)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Stopped.")

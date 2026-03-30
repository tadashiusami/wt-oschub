"""
wt_oschub.py
WebTransport (HTTP/3) OSC Relay Server
License: GNU GPL v3
"""

import asyncio
import logging
import argparse
import random
import string
import struct
from collections import defaultdict
from urllib.parse import urlparse, parse_qs
from aioquic.asyncio import serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import (
    DatagramReceived, 
    H3Event, 
    HeadersReceived, 
    WebTransportStreamDataReceived
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("oschub")

def encode_varint(value: int) -> bytes:
    """Encodes an integer as a QUIC/HTTP3 variable-length integer."""
    if value <= 63: return bytes([value])
    elif value <= 16383: return ((value | 0x4000).to_bytes(2, 'big'))
    elif value <= 1073741823: return ((value | 0x80000000).to_bytes(4, 'big'))
    else: return ((value | 0xC000000000000000).to_bytes(8, 'big'))

def generate_client_id() -> str:
    """Generates a short random alphanumeric client ID (e.g. 'a3f2')."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))

def encode_osc_string(s: str) -> bytes:
    """Encodes a string in OSC format (null-terminated, padded to 4 bytes)."""
    b = s.encode('utf-8') + b'\x00'
    pad = (4 - len(b) % 4) % 4
    return b + b'\x00' * pad

def build_osc_message(address: str, *args) -> bytes:
    """Builds a minimal OSC message with string arguments."""
    msg = encode_osc_string(address)
    type_tag = ',' + 's' * len(args)
    msg += encode_osc_string(type_tag)
    for arg in args:
        msg += encode_osc_string(str(arg))
    return msg

def parse_osc_address(data: bytes) -> str:
    """Extracts the OSC address from a raw OSC message."""
    try:
        end = data.index(b'\x00')
        return data[:end].decode('utf-8')
    except Exception:
        return ''

def rewrite_osc_address(data: bytes, client_id: str, original_address: str) -> bytes:
    """Rewrites the OSC address to /remote/<client_id>/<original_address>.

    The original address portion (padded to 4-byte boundary) is replaced with
    the new address. All arguments following the address are preserved as-is.
    OSC bundles are handled by rewrite_bundle.
    """
    try:
        # Calculate the padded length of the original address
        orig_len = len(original_address.encode('utf-8')) + 1  # +1 for null terminator
        orig_padded = orig_len + (4 - orig_len % 4) % 4

        # Build new address: /remote/<client_id>/<original_address> (strip leading '/')
        new_address = f'/remote/{client_id}/{original_address.lstrip("/")}'
        new_address_bytes = encode_osc_string(new_address)

        # Return new address + everything after the original address
        return new_address_bytes + data[orig_padded:]
    except Exception:
        return data


def rewrite_bundle(data: bytes, client_id: str) -> bytes:
    """Recursively rewrite OSC addresses within an OSC bundle.

    Preserves the bundle header (including timetag) and rewrites each
    contained OSC message address. Nested bundles are handled recursively.
    Returns the original data unchanged on any parse error.
    """
    if len(data) < 16:
        return data
    # '#bundle\0' (8 bytes) + timetag (8 bytes)
    header = data[:16]
    pos = 16
    result = header
    while pos + 4 <= len(data):
        size = struct.unpack('>I', data[pos:pos + 4])[0]
        pos += 4
        if pos + size > len(data):
            break
        elem = data[pos:pos + size]
        pos += size
        if elem[:7] == b'#bundle':
            rewritten_elem = rewrite_bundle(elem, client_id)
        else:
            orig_addr = parse_osc_address(elem)
            rewritten_elem = rewrite_osc_address(elem, client_id, orig_addr)
        result += struct.pack('>I', len(rewritten_elem)) + rewritten_elem
    return result

class OSCHubProtocol(QuicConnectionProtocol):
    # {session_id: {client_id: protocol}}
    sessions = defaultdict(dict)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._http = H3Connection(self._quic, enable_webtransport=True)
        self.session_id = None
        self.client_id = None
        self.display_name = None
        self.webtransport_stream_id = None

    def quic_event_received(self, event: H3Event):
        if self._http is None:
            return

        for http_event in self._http.handle_event(event):
            # 1. Establish WebTransport session via CONNECT request
            if isinstance(http_event, HeadersReceived):
                headers = dict(http_event.headers)
                path = headers.get(b":path", b"/").decode()
                params = parse_qs(urlparse(path).query)
                session_id = params.get('id', [''])[0]

                if not session_id:
                    continue

                self.webtransport_stream_id = http_event.stream_id

                # Generate a unique client ID within the session
                existing_ids = set(self.sessions[session_id].keys())
                self.client_id = generate_client_id()
                while self.client_id in existing_ids:
                    self.client_id = generate_client_id()

                # Determine display name (default: assigned client ID)
                raw_name = params.get('name', [''])[0].strip()
                display_name = raw_name if raw_name else self.client_id

                # Reject duplicate display names within the session
                existing_names = {p.display_name for p in self.sessions[session_id].values()}
                if display_name in existing_names:
                    self._http.send_headers(
                        stream_id=http_event.stream_id,
                        headers=[(b":status", b"409")]
                    )
                    self.transmit()
                    logger.warning(f"[!] Rejected duplicate name '{display_name}' in session '{session_id}'")
                    continue

                self.session_id = session_id
                self.display_name = display_name
                self.sessions[self.session_id][self.client_id] = self

                # Accept the WebTransport session
                self._http.send_headers(
                    stream_id=http_event.stream_id,
                    headers=[
                        (b":status", b"200"),
                        (b"sec-webtransport-http3-draft", b"draft02")
                    ]
                )

                # Send /welcome with client ID and display name to this client only
                welcome_msg = build_osc_message('/welcome', self.client_id, self.display_name)
                self._send_to_self(welcome_msg)

                logger.info(f"--- [JOIN] Session: {self.session_id} | ID: {self.client_id} | Name: {self.display_name} ---")

            # 2. Handle Datagrams (Low-latency OSC)
            elif isinstance(http_event, DatagramReceived):
                address = parse_osc_address(http_event.data)
                logger.debug(f"Datagram received: {address} ({len(http_event.data)} bytes)")
                if address == '/who':
                    # Hub-only: reply with participant list, do not broadcast
                    self._handle_who()
                else:
                    self.broadcast_data(http_event.data, is_datagram=True)

            # 3. Handle Unidirectional Streams (Reliable OSC — SynthDef, Buffer, Sync)
            elif isinstance(http_event, WebTransportStreamDataReceived):
                address = parse_osc_address(http_event.data)
                logger.info(f"Stream received: {address} ({len(http_event.data)} bytes)")
                if address == '/who':
                    # Hub-only: reply with participant list, do not broadcast
                    self._handle_who()
                else:
                    self.broadcast_data(http_event.data, is_datagram=False)

    def _send_to_self(self, data: bytes):
        """Sends an OSC message to this client only via Datagram."""
        try:
            self._http.send_datagram(self.webtransport_stream_id, data)
            self.transmit()
        except Exception as e:
            logger.error(f"Send-to-self error: {e}")

    def _handle_who(self):
        """Replies to the sender with the list of display names in the session."""
        if not self.session_id:
            return
        display_names = [p.display_name for p in self.sessions[self.session_id].values()]
        reply = build_osc_message('/who/reply', *display_names)
        self._send_to_self(reply)
        logger.info(f"[/who] Replied to '{self.display_name}' with {display_names}")

    def broadcast_data(self, data, is_datagram=True):
        """Relays received data to all other clients in the same session.

        The OSC address is rewritten to /remote/<display_name>/<original_address>
        so that recipients can identify the sender and route messages via OSCdef.
        """
        if not self.session_id:
            return

        # Rewrite OSC address once for all recipients
        if data[:7] == b'#bundle':
            rewritten = rewrite_bundle(data, self.display_name)
        else:
            original_address = parse_osc_address(data)
            rewritten = rewrite_osc_address(data, self.display_name, original_address)

        clients = self.sessions.get(self.session_id, {})

        for cid, client in clients.items():
            if client is not self:
                try:
                    if is_datagram:
                        client._http.send_datagram(client.webtransport_stream_id, rewritten)
                    else:
                        out_id = client._quic.get_next_available_stream_id(is_unidirectional=True)
                        header = encode_varint(0x54) + encode_varint(client.webtransport_stream_id)
                        client._quic.send_stream_data(stream_id=out_id, data=header + rewritten, end_stream=True)
                    client.transmit()
                except Exception as e:
                    logger.error(f"Relay error in session {self.session_id}: {e}")

    def connection_lost(self, exc):
        """Clean up session data when a client disconnects."""
        if self.session_id and self.client_id:
            self.sessions[self.session_id].pop(self.client_id, None)
            logger.info(f"--- [LEAVE] Session: {self.session_id} | ID: {self.client_id} | Name: {self.display_name} ---")
        super().connection_lost(exc)

async def main():
    parser = argparse.ArgumentParser(description="WebTransport OSC Hub Server")
    parser.add_argument("--host", default="0.0.0.0", help="Listen host")
    parser.add_argument("--port", type=int, default=8443, help="Listen port")
    parser.add_argument("--cert", required=True, help="Path to TLS certificate (fullchain.pem)")
    parser.add_argument("--key", required=True, help="Path to TLS private key (privkey.pem)")
    args = parser.parse_args()

    configuration = QuicConfiguration(
        is_client=False,
        alpn_protocols=H3_ALPN,
        max_datagram_frame_size=1500
    )
    configuration.load_cert_chain(certfile=args.cert, keyfile=args.key)

    logger.info(f"Starting WebTransport OSC Hub on {args.host}:{args.port}...")
    await serve(
        args.host,
        args.port,
        configuration=configuration,
        create_protocol=OSCHubProtocol
    )
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped.")

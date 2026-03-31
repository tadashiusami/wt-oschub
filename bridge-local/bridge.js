/*
 * bridge.js
 * Local UDP-WebSocket Bridge for SuperCollider and WebTransport
 * * Part of the WebTransport OSC Hub Project
 * License: GNU GPL v3
 */

const dgram = require('dgram');
const WebSocket = require('ws');

// --- Configuration (CLI args: --sc-port, --osc-port, --ws-port) ---
function parseArgs() {
    const args = process.argv.slice(2);
    const result = { 'sc-port': 57120, 'osc-port': 57121, 'ws-port': 8080 };
    for (let i = 0; i < args.length; i++) {
        const m = args[i].match(/^--(\S+)$/);
        if (m && result[m[1]] !== undefined && args[i + 1]) {
            const v = parseInt(args[++i], 10);
            if (!isNaN(v)) result[m[1]] = v;
        }
    }
    return result;
}
const opts = parseArgs();
const UDP_SEND_PORT   = opts['sc-port'];   // Target: SuperCollider (sclang) default port
const UDP_LISTEN_PORT = opts['osc-port'];  // Local: UDP port for bridge.js to receive from SC
const WS_PORT         = opts['ws-port'];   // Local: WebSocket port for index.html connection

// 1. Initialize UDP Socket for SuperCollider communication
const udp = dgram.createSocket('udp4');

// 2. Initialize WebSocket Server for browser communication
const wss = new WebSocket.Server({ port: WS_PORT });
const browserClients = new Set();

/**
 * [A] Relay: SuperCollider -> Browser
 * Listens for OSC messages from SC and forwards them to all connected browsers.
 */
udp.on('message', (msg, rinfo) => {
    if (browserClients.size === 0) {
        return;
    }
    for (const client of browserClients) {
        if (client.readyState === WebSocket.OPEN) {
            client.send(msg);
        }
    }
});

/**
 * [B] Relay: Browser -> SuperCollider
 * Receives OSC messages from the browser and forwards them to SC via UDP.
 */
wss.on('connection', (ws) => {
    console.log(`--- [JOIN] Browser connected to Bridge (total: ${browserClients.size + 1}) ---`);
    browserClients.add(ws);

    ws.on('message', (data) => {
        udp.send(data, UDP_SEND_PORT, '127.0.0.1', (err) => {
            if (err) {
                console.error('SC Send Error:', err);
            }
        });
    });

    ws.on('close', () => {
        browserClients.delete(ws);
        console.log(`--- [LEAVE] Browser disconnected (total: ${browserClients.size}) ---`);
    });

    ws.on('error', (err) => {
        console.error('WebSocket Error:', err);
        browserClients.delete(ws);
    });
});

// Start UDP listener
udp.bind(UDP_LISTEN_PORT, () => {
    console.log(` - Listening for SC on UDP:${UDP_LISTEN_PORT}`);
});

udp.on('error', (err) => {
    console.error(`UDP error: ${err.message}`);
    if (err.code === 'EADDRINUSE') {
        console.error(`Port ${UDP_LISTEN_PORT} is already in use. Is another bridge running?`);
        process.exit(1);
    }
});

console.log(`Bridge active:`);
console.log(` - Forwarding to SC on UDP:${UDP_SEND_PORT}`);
console.log(` - WebSocket for index.html on port:${WS_PORT}`);
/*
 * bridge.js
 * Local UDP-WebSocket Bridge for SuperCollider and WebTransport
 * * Part of the WebTransport OSC Hub Project
 * License: GNU GPL v3
 */

const dgram = require('dgram');
const WebSocket = require('ws');

// --- Configuration ---
const UDP_SEND_PORT = 57120;    // Target: SuperCollider (sclang) default port
const UDP_LISTEN_PORT = 57121;  // Local: UDP port for bridge.js to receive from SC
const WS_PORT = 8080;           // Local: WebSocket port for index.html connection

// 1. Initialize UDP Socket for SuperCollider communication
const udp = dgram.createSocket('udp4');

// 2. Initialize WebSocket Server for browser communication
const wss = new WebSocket.Server({ port: WS_PORT });
let browserClient = null;

/**
 * [A] Relay: SuperCollider -> Browser
 * Listens for OSC messages from SC and forwards them to the browser via WebSocket.
 */
udp.on('message', (msg, rinfo) => {
    console.log(`[UDP IN] From SC: ${msg.length} bytes`);

    // Forward the binary message (Buffer) to the connected browser client
    if (browserClient && browserClient.readyState === WebSocket.OPEN) {
        browserClient.send(msg);
        console.log(' -> Relayed to WebTransport (via index.html)');
    } else {
        console.log(' !! Relay failed: Browser not connected via WebSocket');
    }
});

/**
 * [B] Relay: Browser -> SuperCollider
 * Receives OSC messages from the browser and forwards them to SC via UDP.
 */
wss.on('connection', (ws) => {
    console.log('--- [JOIN] Browser connected to Bridge ---');
    browserClient = ws;

    ws.on('message', (data) => {
        // 'data' contains the binary OSC packet received via WebTransport
        console.log(`[WS IN] From WebTransport: ${data.length} bytes`);

        // Relay to local SuperCollider instance
        udp.send(data, UDP_SEND_PORT, '127.0.0.1', (err) => {
            if (err) {
                console.error('SC Send Error:', err);
            } else {
                console.log(` -> Relayed to SC Port ${UDP_SEND_PORT}`);
            }
        });
    });

    ws.on('close', () => {
        console.log('--- [LEAVE] Browser disconnected ---');
        browserClient = null;
    });

    ws.on('error', (err) => {
        console.error('WebSocket Error:', err);
    });
});

// Start UDP listener
udp.bind(UDP_LISTEN_PORT);

console.log(`Bridge active:`);
console.log(` - Listening for SC on UDP:${UDP_LISTEN_PORT}`);
console.log(` - Forwarding to SC on UDP:${UDP_SEND_PORT}`);
console.log(` - WebSocket for index.html on port:${WS_PORT}`);
import { WebSocketServer } from 'ws';

const wss = new WebSocketServer({ port: 8080 });
wss.on('connection', (ws) => ws.send('hello'));


import { createClient } from 'redis';

const cache = createClient({ url: process.env.REDIS_URL });
await cache.set(`sess:${id}`, token, { EX: 3600 });

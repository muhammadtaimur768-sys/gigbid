import express from 'express';

const app = express();
app.use(express.json());
app.get('/health', (_req, res) => res.json({ ok: true }));


import { createServer } from 'node:http';

createServer((req, res) => res.end('ok')).listen(3000);

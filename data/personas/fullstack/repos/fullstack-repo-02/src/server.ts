import { createClient } from 'redis';

const cache = createClient({ url: process.env.REDIS_URL });
await cache.set(`sess:${id}`, token, { EX: 3600 });


import { createServer } from 'node:http';

createServer((req, res) => res.end('ok')).listen(3000);


export interface Invoice {
  id: string;
  amountCents: number;
  status: 'draft' | 'paid';
}

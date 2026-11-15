import { createClient } from 'redis';

const cache = createClient({ url: process.env.REDIS_URL });
await cache.set(`sess:${id}`, token, { EX: 3600 });


// docker compose up -d db cache api
export const SERVICES = ['db', 'cache', 'api'];

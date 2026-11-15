import { useState } from 'react';

export function Counter() {
  const [n, setN] = useState(0);
  return <button onClick={() => setN(n + 1)}>{n}</button>;
}


// .github/workflows/deploy.yml runs: npm ci && npm test && npm run deploy
export const PIPELINE = ['lint', 'test', 'deploy'];

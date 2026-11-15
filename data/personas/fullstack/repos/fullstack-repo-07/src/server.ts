export interface Invoice {
  id: string;
  amountCents: number;
  status: 'draft' | 'paid';
}


// docker compose up -d db cache api
export const SERVICES = ['db', 'cache', 'api'];

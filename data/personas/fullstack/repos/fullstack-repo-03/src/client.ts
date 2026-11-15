export interface Invoice {
  id: string;
  amountCents: number;
  status: 'draft' | 'paid';
}


import { PrismaClient } from '@prisma/client';

const db = new PrismaClient();
const user = await db.user.findUnique({ where: { email } });

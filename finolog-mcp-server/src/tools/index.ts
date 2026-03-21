import { ToolDefinition, ToolHandler } from '../types/tools.js';
import { bizTools, bizHandlers } from './biz/index.js';
import { accountTools, accountHandlers } from './account/index.js';
import { transactionTools, transactionHandlers } from './transaction/index.js';
import { categoryTools, categoryHandlers } from './category/index.js';
import { contractorTools, contractorHandlers } from './contractor/index.js';
import { companyTools, companyHandlers } from './company/index.js';
import { projectTools, projectHandlers } from './project/index.js';
import { requisiteTools, requisiteHandlers } from './requisite/index.js';
import { debtTools, debtHandlers } from './debt/index.js';
import { orderTools, orderHandlers } from './order/index.js';
import { documentTools, documentHandlers } from './document/index.js';
import { itemTools, itemHandlers } from './item/index.js';
import { packageTools, packageHandlers } from './package/index.js';
import { packageItemTools, packageItemHandlers } from './package-item/index.js';
import { commentTools, commentHandlers } from './comment/index.js';
import { currencyTools, currencyHandlers } from './currency/index.js';
import { unitTools, unitHandlers } from './unit/index.js';
import { userTools, userHandlers } from './user/index.js';

export const allTools: ToolDefinition[] = [
  ...bizTools, ...accountTools, ...transactionTools, ...categoryTools,
  ...contractorTools, ...companyTools, ...projectTools, ...requisiteTools,
  ...debtTools, ...orderTools, ...documentTools, ...itemTools,
  ...packageTools, ...packageItemTools, ...commentTools,
  ...currencyTools, ...unitTools, ...userTools,
];

export const allHandlers: Record<string, ToolHandler> = {
  ...bizHandlers, ...accountHandlers, ...transactionHandlers, ...categoryHandlers,
  ...contractorHandlers, ...companyHandlers, ...projectHandlers, ...requisiteHandlers,
  ...debtHandlers, ...orderHandlers, ...documentHandlers, ...itemHandlers,
  ...packageHandlers, ...packageItemHandlers, ...commentHandlers,
  ...currencyHandlers, ...unitHandlers, ...userHandlers,
};

export function getHandler(name: string): ToolHandler | undefined {
  return allHandlers[name];
}

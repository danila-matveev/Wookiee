import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listDebtsTool, listDebtsHandler } from './list-debts.js';
import { createDebtTool, createDebtHandler } from './create-debt.js';
import { getDebtTool, getDebtHandler } from './get-debt.js';
import { updateDebtTool, updateDebtHandler } from './update-debt.js';
import { deleteDebtTool, deleteDebtHandler } from './delete-debt.js';
import { deleteDebtsBulkTool, deleteDebtsBulkHandler } from './delete-debts-bulk.js';

export const debtTools: ToolDefinition[] = [
  listDebtsTool,
  createDebtTool,
  getDebtTool,
  updateDebtTool,
  deleteDebtTool,
  deleteDebtsBulkTool,
];

export const debtHandlers: Record<string, ToolHandler> = {
  [listDebtsTool.name]: listDebtsHandler,
  [createDebtTool.name]: createDebtHandler,
  [getDebtTool.name]: getDebtHandler,
  [updateDebtTool.name]: updateDebtHandler,
  [deleteDebtTool.name]: deleteDebtHandler,
  [deleteDebtsBulkTool.name]: deleteDebtsBulkHandler,
};

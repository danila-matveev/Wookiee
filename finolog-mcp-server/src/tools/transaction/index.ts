import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listTransactionsTool, listTransactionsHandler } from './list-transactions.js';
import { createTransactionTool, createTransactionHandler } from './create-transaction.js';
import { getTransactionTool, getTransactionHandler } from './get-transaction.js';
import { updateTransactionTool, updateTransactionHandler } from './update-transaction.js';
import { deleteTransactionTool, deleteTransactionHandler } from './delete-transaction.js';
import { splitTransactionTool, splitTransactionHandler } from './split-transaction.js';
import { updateSplitTool, updateSplitHandler } from './update-split.js';
import { deleteSplitTool, deleteSplitHandler } from './delete-split.js';

export const transactionTools: ToolDefinition[] = [
  listTransactionsTool,
  createTransactionTool,
  getTransactionTool,
  updateTransactionTool,
  deleteTransactionTool,
  splitTransactionTool,
  updateSplitTool,
  deleteSplitTool,
];

export const transactionHandlers: Record<string, ToolHandler> = {
  [listTransactionsTool.name]: listTransactionsHandler,
  [createTransactionTool.name]: createTransactionHandler,
  [getTransactionTool.name]: getTransactionHandler,
  [updateTransactionTool.name]: updateTransactionHandler,
  [deleteTransactionTool.name]: deleteTransactionHandler,
  [splitTransactionTool.name]: splitTransactionHandler,
  [updateSplitTool.name]: updateSplitHandler,
  [deleteSplitTool.name]: deleteSplitHandler,
};

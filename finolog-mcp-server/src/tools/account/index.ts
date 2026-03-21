import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listAccountsTool, listAccountsHandler } from './list-accounts.js';
import { createAccountTool, createAccountHandler } from './create-account.js';
import { getAccountTool, getAccountHandler } from './get-account.js';
import { updateAccountTool, updateAccountHandler } from './update-account.js';
import { deleteAccountTool, deleteAccountHandler } from './delete-account.js';

export const accountTools: ToolDefinition[] = [
  listAccountsTool,
  createAccountTool,
  getAccountTool,
  updateAccountTool,
  deleteAccountTool,
];

export const accountHandlers: Record<string, ToolHandler> = {
  [listAccountsTool.name]: listAccountsHandler,
  [createAccountTool.name]: createAccountHandler,
  [getAccountTool.name]: getAccountHandler,
  [updateAccountTool.name]: updateAccountHandler,
  [deleteAccountTool.name]: deleteAccountHandler,
};

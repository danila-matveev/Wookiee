import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { getUserTool, getUserHandler } from './get-user.js';
import { updateUserTool, updateUserHandler } from './update-user.js';

export const userTools: ToolDefinition[] = [
  getUserTool,
  updateUserTool,
];

export const userHandlers: Record<string, ToolHandler> = {
  [getUserTool.name]: getUserHandler,
  [updateUserTool.name]: updateUserHandler,
};

import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listItemsTool, listItemsHandler } from './list-items.js';
import { createItemTool, createItemHandler } from './create-item.js';
import { getItemTool, getItemHandler } from './get-item.js';
import { updateItemTool, updateItemHandler } from './update-item.js';
import { deleteItemTool, deleteItemHandler } from './delete-item.js';

export const itemTools: ToolDefinition[] = [
  listItemsTool,
  createItemTool,
  getItemTool,
  updateItemTool,
  deleteItemTool,
];

export const itemHandlers: Record<string, ToolHandler> = {
  [listItemsTool.name]: listItemsHandler,
  [createItemTool.name]: createItemHandler,
  [getItemTool.name]: getItemHandler,
  [updateItemTool.name]: updateItemHandler,
  [deleteItemTool.name]: deleteItemHandler,
};

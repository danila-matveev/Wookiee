import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listOrdersTool, listOrdersHandler } from './list-orders.js';
import { createOrderTool, createOrderHandler } from './create-order.js';
import { getOrderTool, getOrderHandler } from './get-order.js';
import { updateOrderTool, updateOrderHandler } from './update-order.js';
import { deleteOrderTool, deleteOrderHandler } from './delete-order.js';
import { listStatusesTool, listStatusesHandler } from './list-statuses.js';

export const orderTools: ToolDefinition[] = [
  listOrdersTool,
  createOrderTool,
  getOrderTool,
  updateOrderTool,
  deleteOrderTool,
  listStatusesTool,
];

export const orderHandlers: Record<string, ToolHandler> = {
  [listOrdersTool.name]: listOrdersHandler,
  [createOrderTool.name]: createOrderHandler,
  [getOrderTool.name]: getOrderHandler,
  [updateOrderTool.name]: updateOrderHandler,
  [deleteOrderTool.name]: deleteOrderHandler,
  [listStatusesTool.name]: listStatusesHandler,
};

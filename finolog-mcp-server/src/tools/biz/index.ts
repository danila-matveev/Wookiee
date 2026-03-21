import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listBizTool, listBizHandler } from './list-biz.js';
import { createBizTool, createBizHandler } from './create-biz.js';
import { getBizTool, getBizHandler } from './get-biz.js';
import { updateBizTool, updateBizHandler } from './update-biz.js';
import { deleteBizTool, deleteBizHandler } from './delete-biz.js';

export const bizTools: ToolDefinition[] = [
  listBizTool,
  createBizTool,
  getBizTool,
  updateBizTool,
  deleteBizTool,
];

export const bizHandlers: Record<string, ToolHandler> = {
  [listBizTool.name]: listBizHandler,
  [createBizTool.name]: createBizHandler,
  [getBizTool.name]: getBizHandler,
  [updateBizTool.name]: updateBizHandler,
  [deleteBizTool.name]: deleteBizHandler,
};

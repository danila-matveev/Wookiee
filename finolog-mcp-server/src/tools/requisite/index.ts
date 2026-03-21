import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listRequisitesTool, listRequisitesHandler } from './list-requisites.js';
import { createRequisiteTool, createRequisiteHandler } from './create-requisite.js';
import { getRequisiteTool, getRequisiteHandler } from './get-requisite.js';
import { updateRequisiteTool, updateRequisiteHandler } from './update-requisite.js';
import { deleteRequisiteTool, deleteRequisiteHandler } from './delete-requisite.js';

export const requisiteTools: ToolDefinition[] = [
  listRequisitesTool,
  createRequisiteTool,
  getRequisiteTool,
  updateRequisiteTool,
  deleteRequisiteTool,
];

export const requisiteHandlers: Record<string, ToolHandler> = {
  [listRequisitesTool.name]: listRequisitesHandler,
  [createRequisiteTool.name]: createRequisiteHandler,
  [getRequisiteTool.name]: getRequisiteHandler,
  [updateRequisiteTool.name]: updateRequisiteHandler,
  [deleteRequisiteTool.name]: deleteRequisiteHandler,
};

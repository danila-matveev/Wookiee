import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listContractorsTool, listContractorsHandler } from './list-contractors.js';
import { createContractorTool, createContractorHandler } from './create-contractor.js';
import { getContractorTool, getContractorHandler } from './get-contractor.js';
import { updateContractorTool, updateContractorHandler } from './update-contractor.js';
import { deleteContractorTool, deleteContractorHandler } from './delete-contractor.js';
import { createAutoeditorTool, createAutoeditorHandler } from './create-autoeditor.js';

export const contractorTools: ToolDefinition[] = [
  listContractorsTool,
  createContractorTool,
  getContractorTool,
  updateContractorTool,
  deleteContractorTool,
  createAutoeditorTool,
];

export const contractorHandlers: Record<string, ToolHandler> = {
  [listContractorsTool.name]: listContractorsHandler,
  [createContractorTool.name]: createContractorHandler,
  [getContractorTool.name]: getContractorHandler,
  [updateContractorTool.name]: updateContractorHandler,
  [deleteContractorTool.name]: deleteContractorHandler,
  [createAutoeditorTool.name]: createAutoeditorHandler,
};

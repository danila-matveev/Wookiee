import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { createPackageTool, createPackageHandler } from './create-package.js';
import { updatePackageTool, updatePackageHandler } from './update-package.js';
import { deletePackageTool, deletePackageHandler } from './delete-package.js';

export const packageTools: ToolDefinition[] = [
  createPackageTool,
  updatePackageTool,
  deletePackageTool,
];

export const packageHandlers: Record<string, ToolHandler> = {
  [createPackageTool.name]: createPackageHandler,
  [updatePackageTool.name]: updatePackageHandler,
  [deletePackageTool.name]: deletePackageHandler,
};

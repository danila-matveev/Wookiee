import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { addPackageItemTool, addPackageItemHandler } from './add-package-item.js';
import { updatePackageItemTool, updatePackageItemHandler } from './update-package-item.js';
import { deletePackageItemTool, deletePackageItemHandler } from './delete-package-item.js';

export const packageItemTools: ToolDefinition[] = [
  addPackageItemTool,
  updatePackageItemTool,
  deletePackageItemTool,
];

export const packageItemHandlers: Record<string, ToolHandler> = {
  [addPackageItemTool.name]: addPackageItemHandler,
  [updatePackageItemTool.name]: updatePackageItemHandler,
  [deletePackageItemTool.name]: deletePackageItemHandler,
};

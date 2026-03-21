import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listProjectsTool, listProjectsHandler } from './list-projects.js';
import { createProjectTool, createProjectHandler } from './create-project.js';
import { getProjectTool, getProjectHandler } from './get-project.js';
import { updateProjectTool, updateProjectHandler } from './update-project.js';
import { deleteProjectTool, deleteProjectHandler } from './delete-project.js';

export const projectTools: ToolDefinition[] = [
  listProjectsTool,
  createProjectTool,
  getProjectTool,
  updateProjectTool,
  deleteProjectTool,
];

export const projectHandlers: Record<string, ToolHandler> = {
  [listProjectsTool.name]: listProjectsHandler,
  [createProjectTool.name]: createProjectHandler,
  [getProjectTool.name]: getProjectHandler,
  [updateProjectTool.name]: updateProjectHandler,
  [deleteProjectTool.name]: deleteProjectHandler,
};

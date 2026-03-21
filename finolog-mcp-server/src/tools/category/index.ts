import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listCategoriesTool, listCategoriesHandler } from './list-categories.js';
import { createCategoryTool, createCategoryHandler } from './create-category.js';
import { getCategoryTool, getCategoryHandler } from './get-category.js';
import { updateCategoryTool, updateCategoryHandler } from './update-category.js';
import { deleteCategoryTool, deleteCategoryHandler } from './delete-category.js';

export const categoryTools: ToolDefinition[] = [
  listCategoriesTool,
  createCategoryTool,
  getCategoryTool,
  updateCategoryTool,
  deleteCategoryTool,
];

export const categoryHandlers: Record<string, ToolHandler> = {
  [listCategoriesTool.name]: listCategoriesHandler,
  [createCategoryTool.name]: createCategoryHandler,
  [getCategoryTool.name]: getCategoryHandler,
  [updateCategoryTool.name]: updateCategoryHandler,
  [deleteCategoryTool.name]: deleteCategoryHandler,
};

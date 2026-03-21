import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listCompaniesTool, listCompaniesHandler } from './list-companies.js';
import { createCompanyTool, createCompanyHandler } from './create-company.js';
import { getCompanyTool, getCompanyHandler } from './get-company.js';
import { updateCompanyTool, updateCompanyHandler } from './update-company.js';
import { deleteCompanyTool, deleteCompanyHandler } from './delete-company.js';

export const companyTools: ToolDefinition[] = [
  listCompaniesTool,
  createCompanyTool,
  getCompanyTool,
  updateCompanyTool,
  deleteCompanyTool,
];

export const companyHandlers: Record<string, ToolHandler> = {
  [listCompaniesTool.name]: listCompaniesHandler,
  [createCompanyTool.name]: createCompanyHandler,
  [getCompanyTool.name]: getCompanyHandler,
  [updateCompanyTool.name]: updateCompanyHandler,
  [deleteCompanyTool.name]: deleteCompanyHandler,
};

import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listDocumentsTool, listDocumentsHandler } from './list-documents.js';
import { createDocumentTool, createDocumentHandler } from './create-document.js';
import { getDocumentTool, getDocumentHandler } from './get-document.js';
import { updateDocumentTool, updateDocumentHandler } from './update-document.js';
import { deleteDocumentTool, deleteDocumentHandler } from './delete-document.js';
import { getDocumentPdfTool, getDocumentPdfHandler } from './get-document-pdf.js';

export const documentTools: ToolDefinition[] = [
  listDocumentsTool,
  createDocumentTool,
  getDocumentTool,
  updateDocumentTool,
  deleteDocumentTool,
  getDocumentPdfTool,
];

export const documentHandlers: Record<string, ToolHandler> = {
  [listDocumentsTool.name]: listDocumentsHandler,
  [createDocumentTool.name]: createDocumentHandler,
  [getDocumentTool.name]: getDocumentHandler,
  [updateDocumentTool.name]: updateDocumentHandler,
  [deleteDocumentTool.name]: deleteDocumentHandler,
  [getDocumentPdfTool.name]: getDocumentPdfHandler,
};

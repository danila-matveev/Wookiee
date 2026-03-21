import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listCommentsTool, listCommentsHandler } from './list-comments.js';
import { createCommentTool, createCommentHandler } from './create-comment.js';

export const commentTools: ToolDefinition[] = [
  listCommentsTool,
  createCommentTool,
];

export const commentHandlers: Record<string, ToolHandler> = {
  [listCommentsTool.name]: listCommentsHandler,
  [createCommentTool.name]: createCommentHandler,
};

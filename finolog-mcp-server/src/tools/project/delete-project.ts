import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deleteProjectTool: ToolDefinition = {
  name: 'finolog_delete_project',
  description: 'Удалить проект по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID проекта',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const deleteProjectHandler: ToolHandler = async (params) => {
  try {
    logger.info('Удаление проекта', params);
    const { biz_id, id } = params as any;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/project/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete project', { error });
    return formatError(error, 'finolog_delete_project');
  }
};

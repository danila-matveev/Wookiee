import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getProjectTool: ToolDefinition = {
  name: 'finolog_get_project',
  description: 'Получить проект по ID',
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

export const getProjectHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение проекта', params);
    const { biz_id, id } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/project/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get project', { error });
    return formatError(error, 'finolog_get_project');
  }
};

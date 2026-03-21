import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateProjectTool: ToolDefinition = {
  name: 'finolog_update_project',
  description: 'Обновить проект по ID',
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
      name: {
        type: 'string',
        description: 'Название проекта',
      },
      currency_id: {
        type: 'number',
        description: 'ID валюты',
      },
      status: {
        type: 'string',
        description: 'Статус проекта: active, on hold, completed, archive',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const updateProjectHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление проекта', params);
    const { biz_id, id, ...body } = params as any;
    const response = await finologClient.put(`/v1/biz/${biz_id}/project/${id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update project', { error });
    return formatError(error, 'finolog_update_project');
  }
};

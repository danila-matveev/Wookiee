import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createProjectTool: ToolDefinition = {
  name: 'finolog_create_project',
  description: 'Создать проект в бизнесе',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
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
    required: ['biz_id', 'name', 'currency_id'],
  },
};

export const createProjectHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание проекта', params);
    const { biz_id, ...body } = params as any;
    const response = await finologClient.post(`/v1/biz/${biz_id}/project`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create project', { error });
    return formatError(error, 'finolog_create_project');
  }
};

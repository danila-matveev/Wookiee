import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createBizTool: ToolDefinition = {
  name: 'finolog_create_biz',
  description: 'Создать новый бизнес в Finolog',
  inputSchema: {
    type: 'object',
    properties: {
      name: {
        type: 'string',
        description: 'Название бизнеса',
      },
      base_currency_id: {
        type: 'number',
        description: 'ID базовой валюты',
      },
    },
    required: ['name', 'base_currency_id'],
  },
};

export const createBizHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание бизнеса', params);
    const response = await finologClient.post('/v1/biz', params);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create business', { error });
    return formatError(error, 'finolog_create_biz');
  }
};

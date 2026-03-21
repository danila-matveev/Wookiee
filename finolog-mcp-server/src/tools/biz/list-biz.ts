import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listBizTool: ToolDefinition = {
  name: 'finolog_list_biz',
  description: 'Получить список всех бизнесов в Finolog',
  inputSchema: {
    type: 'object',
    properties: {},
    required: [],
  },
};

export const listBizHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка бизнесов', params);
    const response = await finologClient.get('/v1/biz');
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list businesses', { error });
    return formatError(error, 'finolog_list_biz');
  }
};

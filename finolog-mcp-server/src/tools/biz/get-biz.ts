import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getBizTool: ToolDefinition = {
  name: 'finolog_get_biz',
  description: 'Получить информацию о бизнесе по ID',
  inputSchema: {
    type: 'object',
    properties: {
      id: {
        type: 'number',
        description: 'ID бизнеса',
      },
    },
    required: ['id'],
  },
};

export const getBizHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение бизнеса', params);
    const { id } = params;
    const response = await finologClient.get(`/v1/biz/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get business', { error });
    return formatError(error, 'finolog_get_biz');
  }
};

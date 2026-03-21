import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getAccountTool: ToolDefinition = {
  name: 'finolog_get_account',
  description: 'Получить информацию о счёте по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID счёта',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const getAccountHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение счёта', params);
    const { biz_id, id } = params;
    const response = await finologClient.get(`/v1/biz/${biz_id}/account/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get account', { error });
    return formatError(error, 'finolog_get_account');
  }
};

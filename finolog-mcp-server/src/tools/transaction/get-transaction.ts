import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getTransactionTool: ToolDefinition = {
  name: 'finolog_get_transaction',
  description: 'Получить транзакцию по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID транзакции',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const getTransactionHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение транзакции', params);
    const { biz_id, id } = params;
    const response = await finologClient.get(`/v1/biz/${biz_id}/transaction/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get transaction', { error });
    return formatError(error, 'finolog_get_transaction');
  }
};

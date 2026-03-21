import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const splitTransactionTool: ToolDefinition = {
  name: 'finolog_split_transaction',
  description: 'Разделить транзакцию на несколько категорий',
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
      items: {
        type: 'array',
        description: 'Массив частей разделения',
        items: {
          type: 'object',
          properties: {
            category_id: {
              type: 'number',
              description: 'ID категории ДДС',
            },
            value: {
              type: 'number',
              description: 'Сумма части',
            },
          },
          required: ['category_id', 'value'],
        },
      },
    },
    required: ['biz_id', 'id', 'items'],
  },
};

export const splitTransactionHandler: ToolHandler = async (params) => {
  try {
    logger.info('Разделение транзакции', params);
    const { biz_id, id, ...body } = params;
    const response = await finologClient.post(`/v1/biz/${biz_id}/transaction/${id}/split`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to split transaction', { error });
    return formatError(error, 'finolog_split_transaction');
  }
};

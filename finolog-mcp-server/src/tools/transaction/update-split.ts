import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateSplitTool: ToolDefinition = {
  name: 'finolog_update_split',
  description: 'Обновить разделение транзакции',
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

export const updateSplitHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление разделения транзакции', params);
    const { biz_id, id, ...body } = params;
    const response = await finologClient.put(`/v1/biz/${biz_id}/transaction/${id}/split`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update split', { error });
    return formatError(error, 'finolog_update_split');
  }
};

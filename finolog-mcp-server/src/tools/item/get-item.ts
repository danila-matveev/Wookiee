import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getItemTool: ToolDefinition = {
  name: 'finolog_get_item',
  description: 'Получить товар/услугу по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID товара/услуги',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const getItemHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение товара/услуги', params);
    const { biz_id, id } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/orders/item/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get item', { error });
    return formatError(error, 'finolog_get_item');
  }
};

import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getOrderTool: ToolDefinition = {
  name: 'finolog_get_order',
  description: 'Получить заказ по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      order_id: {
        type: 'number',
        description: 'ID заказа',
      },
    },
    required: ['biz_id', 'order_id'],
  },
};

export const getOrderHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение заказа', params);
    const { biz_id, order_id } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/orders/order/${order_id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get order', { error });
    return formatError(error, 'finolog_get_order');
  }
};

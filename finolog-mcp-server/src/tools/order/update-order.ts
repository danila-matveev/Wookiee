import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateOrderTool: ToolDefinition = {
  name: 'finolog_update_order',
  description: 'Обновить заказ по ID',
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
      type: {
        type: 'string',
        description: 'Тип заказа: in или out',
      },
      seller_id: {
        type: 'number',
        description: 'ID продавца',
      },
      buyer_id: {
        type: 'number',
        description: 'ID покупателя',
      },
      description: {
        type: 'string',
        description: 'Описание заказа',
      },
      status: {
        type: 'string',
        description: 'Статус заказа',
      },
    },
    required: ['biz_id', 'order_id'],
  },
};

export const updateOrderHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление заказа', params);
    const { biz_id, order_id, ...body } = params as any;
    const response = await finologClient.put(`/v1/biz/${biz_id}/orders/order/${order_id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update order', { error });
    return formatError(error, 'finolog_update_order');
  }
};

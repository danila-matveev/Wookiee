import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createOrderTool: ToolDefinition = {
  name: 'finolog_create_order',
  description: 'Создать заказ в бизнесе',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      type: {
        type: 'string',
        description: 'Тип заказа: in (входящий) или out (исходящий)',
      },
      seller_id: {
        type: 'number',
        description: 'ID продавца',
      },
      buyer_id: {
        type: 'number',
        description: 'ID покупателя',
      },
      cost_package: {
        type: 'object',
        description: 'Пакет стоимости',
      },
      description: {
        type: 'string',
        description: 'Описание заказа',
      },
    },
    required: ['biz_id', 'type', 'seller_id', 'buyer_id'],
  },
};

export const createOrderHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание заказа', params);
    const { biz_id, ...body } = params as any;
    const response = await finologClient.post(`/v1/biz/${biz_id}/orders/order`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create order', { error });
    return formatError(error, 'finolog_create_order');
  }
};

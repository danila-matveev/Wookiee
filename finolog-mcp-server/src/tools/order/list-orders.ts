import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listOrdersTool: ToolDefinition = {
  name: 'finolog_list_orders',
  description: 'Получить список заказов бизнеса',
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
      status: {
        type: 'string',
        description: 'Статус заказа',
      },
      date_from: {
        type: 'string',
        description: 'Дата начала (YYYY-MM-DD)',
      },
      date_to: {
        type: 'string',
        description: 'Дата окончания (YYYY-MM-DD)',
      },
      page: {
        type: 'number',
        description: 'Номер страницы',
      },
      per_page: {
        type: 'number',
        description: 'Количество на странице',
      },
    },
    required: ['biz_id'],
  },
};

export const listOrdersHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка заказов', params);
    const { biz_id, ...query } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/orders/order`, query);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list orders', { error });
    return formatError(error, 'finolog_list_orders');
  }
};

import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listStatusesTool: ToolDefinition = {
  name: 'finolog_list_order_statuses',
  description: 'Получить список статусов заказов',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
    },
    required: ['biz_id'],
  },
};

export const listStatusesHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка статусов заказов', params);
    const { biz_id } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/orders/status`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list order statuses', { error });
    return formatError(error, 'finolog_list_order_statuses');
  }
};

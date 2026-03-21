import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listItemsTool: ToolDefinition = {
  name: 'finolog_list_items',
  description: 'Получить список товаров/услуг бизнеса',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      query: {
        type: 'string',
        description: 'Поисковый запрос',
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

export const listItemsHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка товаров/услуг', params);
    const { biz_id, ...query } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/orders/item`, query);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list items', { error });
    return formatError(error, 'finolog_list_items');
  }
};

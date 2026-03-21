import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateItemTool: ToolDefinition = {
  name: 'finolog_update_item',
  description: 'Обновить товар/услугу по ID',
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
      name: {
        type: 'string',
        description: 'Название товара/услуги',
      },
      price: {
        type: 'number',
        description: 'Цена',
      },
      currency_id: {
        type: 'number',
        description: 'ID валюты',
      },
      type: {
        type: 'string',
        description: 'Тип: product или service',
      },
      unit_id: {
        type: 'number',
        description: 'ID единицы измерения',
      },
      description: {
        type: 'string',
        description: 'Описание',
      },
    },
    required: ['biz_id', 'id', 'name', 'price', 'currency_id'],
  },
};

export const updateItemHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление товара/услуги', params);
    const { biz_id, id, ...body } = params as any;
    const response = await finologClient.put(`/v1/biz/${biz_id}/orders/item/${id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update item', { error });
    return formatError(error, 'finolog_update_item');
  }
};

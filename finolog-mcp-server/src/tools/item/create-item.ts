import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createItemTool: ToolDefinition = {
  name: 'finolog_create_item',
  description: 'Создать товар/услугу в бизнесе',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
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
    required: ['biz_id', 'name', 'price', 'currency_id'],
  },
};

export const createItemHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание товара/услуги', params);
    const { biz_id, ...body } = params as any;
    const response = await finologClient.post(`/v1/biz/${biz_id}/orders/item`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create item', { error });
    return formatError(error, 'finolog_create_item');
  }
};

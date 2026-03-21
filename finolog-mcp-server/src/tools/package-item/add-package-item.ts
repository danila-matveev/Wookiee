import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const addPackageItemTool: ToolDefinition = {
  name: 'finolog_add_package_item',
  description: 'Добавить позицию в пакет',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: { type: 'number', description: 'ID бизнеса' },
      package_id: { type: 'number', description: 'ID пакета' },
      item_id: { type: 'number', description: 'ID товара/услуги' },
      count: { type: 'number', description: 'Количество' },
      price: { type: 'number', description: 'Цена за единицу' },
      vat: { type: 'number', description: 'НДС' },
    },
    required: ['biz_id', 'package_id', 'item_id', 'count', 'price'],
  },
};

export const addPackageItemHandler: ToolHandler = async (params) => {
  try {
    logger.info('Добавление позиции в пакет', params);
    const { biz_id, package_id, ...body } = params;
    const response = await finologClient.post(`/v1/biz/${biz_id}/orders/package/${package_id}/item`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to add package item', { error });
    return formatError(error, 'finolog_add_package_item');
  }
};

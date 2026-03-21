import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updatePackageItemTool: ToolDefinition = {
  name: 'finolog_update_package_item',
  description: 'Обновить позицию в пакете',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: { type: 'number', description: 'ID бизнеса' },
      package_id: { type: 'number', description: 'ID пакета' },
      package_item_id: { type: 'number', description: 'ID позиции в пакете' },
      count: { type: 'number', description: 'Количество' },
      price: { type: 'number', description: 'Цена за единицу' },
      vat: { type: 'number', description: 'НДС' },
    },
    required: ['biz_id', 'package_id', 'package_item_id'],
  },
};

export const updatePackageItemHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление позиции в пакете', params);
    const { biz_id, package_id, package_item_id, ...body } = params;
    const response = await finologClient.put(`/v1/biz/${biz_id}/orders/package/${package_id}/item/${package_item_id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update package item', { error });
    return formatError(error, 'finolog_update_package_item');
  }
};

import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deletePackageItemTool: ToolDefinition = {
  name: 'finolog_delete_package_item',
  description: 'Удалить позицию из пакета',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: { type: 'number', description: 'ID бизнеса' },
      package_id: { type: 'number', description: 'ID пакета' },
      package_item_id: { type: 'number', description: 'ID позиции в пакете' },
    },
    required: ['biz_id', 'package_id', 'package_item_id'],
  },
};

export const deletePackageItemHandler: ToolHandler = async (params) => {
  try {
    logger.info('Удаление позиции из пакета', params);
    const { biz_id, package_id, package_item_id } = params;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/orders/package/${package_id}/item/${package_item_id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete package item', { error });
    return formatError(error, 'finolog_delete_package_item');
  }
};

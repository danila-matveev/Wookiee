import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deleteItemTool: ToolDefinition = {
  name: 'finolog_delete_item',
  description: 'Удалить товар/услугу по ID',
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
    },
    required: ['biz_id', 'id'],
  },
};

export const deleteItemHandler: ToolHandler = async (params) => {
  try {
    logger.info('Удаление товара/услуги', params);
    const { biz_id, id } = params as any;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/orders/item/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete item', { error });
    return formatError(error, 'finolog_delete_item');
  }
};

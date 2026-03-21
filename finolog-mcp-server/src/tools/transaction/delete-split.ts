import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deleteSplitTool: ToolDefinition = {
  name: 'finolog_delete_split',
  description: 'Отменить разделение транзакции',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID транзакции',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const deleteSplitHandler: ToolHandler = async (params) => {
  try {
    logger.info('Отмена разделения транзакции', params);
    const { biz_id, id } = params;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/transaction/${id}/split`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete split', { error });
    return formatError(error, 'finolog_delete_split');
  }
};

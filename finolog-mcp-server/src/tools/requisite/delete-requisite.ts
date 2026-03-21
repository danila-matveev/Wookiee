import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deleteRequisiteTool: ToolDefinition = {
  name: 'finolog_delete_requisite',
  description: 'Удалить реквизиты по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID реквизитов',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const deleteRequisiteHandler: ToolHandler = async (params) => {
  try {
    logger.info('Удаление реквизитов', params);
    const { biz_id, id } = params as any;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/requisite/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete requisite', { error });
    return formatError(error, 'finolog_delete_requisite');
  }
};

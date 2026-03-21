import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deleteDebtTool: ToolDefinition = {
  name: 'finolog_delete_debt',
  description: 'Удалить долг по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      contractor_id: {
        type: 'number',
        description: 'ID контрагента',
      },
      debt_id: {
        type: 'number',
        description: 'ID долга',
      },
    },
    required: ['biz_id', 'contractor_id', 'debt_id'],
  },
};

export const deleteDebtHandler: ToolHandler = async (params) => {
  try {
    logger.info('Удаление долга', params);
    const { biz_id, contractor_id, debt_id } = params as any;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/contractor/${contractor_id}/debt/${debt_id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete debt', { error });
    return formatError(error, 'finolog_delete_debt');
  }
};

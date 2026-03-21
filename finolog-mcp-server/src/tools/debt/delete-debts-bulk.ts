import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deleteDebtsBulkTool: ToolDefinition = {
  name: 'finolog_delete_debts_bulk',
  description: 'Удалить несколько долгов контрагента',
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
      ids: {
        type: 'string',
        description: 'ID долгов через запятую',
      },
    },
    required: ['biz_id', 'contractor_id', 'ids'],
  },
};

export const deleteDebtsBulkHandler: ToolHandler = async (params) => {
  try {
    logger.info('Массовое удаление долгов', params);
    const { biz_id, contractor_id, ids } = params as any;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/contractor/${contractor_id}/debt`, { ids });
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to bulk delete debts', { error });
    return formatError(error, 'finolog_delete_debts_bulk');
  }
};

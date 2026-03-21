import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getDebtTool: ToolDefinition = {
  name: 'finolog_get_debt',
  description: 'Получить долг по ID',
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

export const getDebtHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение долга', params);
    const { biz_id, contractor_id, debt_id } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/contractor/${contractor_id}/debt/${debt_id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get debt', { error });
    return formatError(error, 'finolog_get_debt');
  }
};

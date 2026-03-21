import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getRequisiteTool: ToolDefinition = {
  name: 'finolog_get_requisite',
  description: 'Получить реквизиты по ID',
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

export const getRequisiteHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение реквизитов', params);
    const { biz_id, id } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/requisite/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get requisite', { error });
    return formatError(error, 'finolog_get_requisite');
  }
};

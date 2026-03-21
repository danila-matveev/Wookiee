import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getContractorTool: ToolDefinition = {
  name: 'finolog_get_contractor',
  description: 'Получить контрагента по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID контрагента',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const getContractorHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение контрагента', params);
    const { biz_id, id } = params;
    const response = await finologClient.get(`/v1/biz/${biz_id}/contractor/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get contractor', { error });
    return formatError(error, 'finolog_get_contractor');
  }
};

import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getCompanyTool: ToolDefinition = {
  name: 'finolog_get_company',
  description: 'Получить юридическое лицо по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID юр. лица',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const getCompanyHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение юр. лица', params);
    const { biz_id, id } = params;
    const response = await finologClient.get(`/v1/biz/${biz_id}/company/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get company', { error });
    return formatError(error, 'finolog_get_company');
  }
};

import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listCompaniesTool: ToolDefinition = {
  name: 'finolog_list_companies',
  description: 'Получить список юридических лиц бизнеса',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
    },
    required: ['biz_id'],
  },
};

export const listCompaniesHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка юр. лиц', params);
    const { biz_id } = params;
    const response = await finologClient.get(`/v1/biz/${biz_id}/company`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list companies', { error });
    return formatError(error, 'finolog_list_companies');
  }
};

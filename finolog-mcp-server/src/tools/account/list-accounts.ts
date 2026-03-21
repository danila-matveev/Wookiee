import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listAccountsTool: ToolDefinition = {
  name: 'finolog_list_accounts',
  description: 'Получить список счетов бизнеса',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      ids: {
        type: 'string',
        description: 'Список ID через запятую для фильтрации',
      },
    },
    required: ['biz_id'],
  },
};

export const listAccountsHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка счетов', params);
    const { biz_id, ...queryParams } = params;
    const response = await finologClient.get(`/v1/biz/${biz_id}/account`, queryParams);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list accounts', { error });
    return formatError(error, 'finolog_list_accounts');
  }
};

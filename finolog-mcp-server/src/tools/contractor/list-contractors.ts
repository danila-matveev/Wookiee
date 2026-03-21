import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listContractorsTool: ToolDefinition = {
  name: 'finolog_list_contractors',
  description: 'Получить список контрагентов бизнеса',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      email: {
        type: 'string',
        description: 'Фильтр по email',
      },
      inn: {
        type: 'string',
        description: 'Фильтр по ИНН',
      },
      query: {
        type: 'string',
        description: 'Поисковый запрос',
      },
      page: {
        type: 'number',
        description: 'Номер страницы',
      },
      per_page: {
        type: 'number',
        description: 'Количество записей на странице',
      },
    },
    required: ['biz_id'],
  },
};

export const listContractorsHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка контрагентов', params);
    const { biz_id, ...queryParams } = params;
    const response = await finologClient.get(`/v1/biz/${biz_id}/contractor`, queryParams);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list contractors', { error });
    return formatError(error, 'finolog_list_contractors');
  }
};

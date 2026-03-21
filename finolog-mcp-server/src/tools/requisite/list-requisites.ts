import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listRequisitesTool: ToolDefinition = {
  name: 'finolog_list_requisites',
  description: 'Получить список реквизитов бизнеса',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      contractor_id: {
        type: 'number',
        description: 'ID контрагента для фильтрации',
      },
      ids: {
        type: 'string',
        description: 'Список ID через запятую',
      },
      is_bizzed: {
        type: 'boolean',
        description: 'Фильтр по принадлежности к бизнесу',
      },
    },
    required: ['biz_id'],
  },
};

export const listRequisitesHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка реквизитов', params);
    const { biz_id, ...query } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/requisite`, query);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list requisites', { error });
    return formatError(error, 'finolog_list_requisites');
  }
};

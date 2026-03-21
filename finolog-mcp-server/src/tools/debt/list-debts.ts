import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listDebtsTool: ToolDefinition = {
  name: 'finolog_list_debts',
  description: 'Получить список долгов контрагента',
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
      date_from: {
        type: 'string',
        description: 'Дата начала (YYYY-MM-DD)',
      },
      date_to: {
        type: 'string',
        description: 'Дата окончания (YYYY-MM-DD)',
      },
      page: {
        type: 'number',
        description: 'Номер страницы',
      },
      per_page: {
        type: 'number',
        description: 'Количество на странице',
      },
    },
    required: ['biz_id', 'contractor_id'],
  },
};

export const listDebtsHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка долгов', params);
    const { biz_id, contractor_id, ...query } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/contractor/${contractor_id}/debt`, query);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list debts', { error });
    return formatError(error, 'finolog_list_debts');
  }
};

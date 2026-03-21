import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listTransactionsTool: ToolDefinition = {
  name: 'finolog_list_transactions',
  description: 'Получить список транзакций бизнеса с фильтрацией',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      date_from: {
        type: 'string',
        description: 'Дата начала периода (YYYY-MM-DD)',
      },
      date_to: {
        type: 'string',
        description: 'Дата окончания периода (YYYY-MM-DD)',
      },
      category_id: {
        type: 'number',
        description: 'ID категории ДДС',
      },
      contractor_id: {
        type: 'number',
        description: 'ID контрагента',
      },
      account_id: {
        type: 'number',
        description: 'ID счёта',
      },
      project_id: {
        type: 'number',
        description: 'ID проекта',
      },
      type: {
        type: 'string',
        description: 'Тип транзакции: in, out, transfer',
      },
      status: {
        type: 'string',
        description: 'Статус: created, reconciled',
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

export const listTransactionsHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка транзакций', params);
    const { biz_id, ...queryParams } = params;
    const response = await finologClient.get(`/v1/biz/${biz_id}/transaction`, queryParams);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list transactions', { error });
    return formatError(error, 'finolog_list_transactions');
  }
};

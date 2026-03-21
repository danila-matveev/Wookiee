import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createTransactionTool: ToolDefinition = {
  name: 'finolog_create_transaction',
  description: 'Создать новую транзакцию в бизнесе',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      date: {
        type: 'string',
        description: 'Дата транзакции (YYYY-MM-DD)',
      },
      value: {
        type: 'number',
        description: 'Сумма транзакции',
      },
      from_id: {
        type: 'number',
        description: 'ID счёта-источника',
      },
      to_id: {
        type: 'number',
        description: 'ID счёта-получателя',
      },
      category_id: {
        type: 'number',
        description: 'ID категории ДДС',
      },
      contractor_id: {
        type: 'number',
        description: 'ID контрагента',
      },
      project_id: {
        type: 'number',
        description: 'ID проекта',
      },
      description: {
        type: 'string',
        description: 'Описание транзакции',
      },
      status: {
        type: 'string',
        description: 'Статус: created, reconciled',
      },
    },
    required: ['biz_id', 'date', 'value'],
  },
};

export const createTransactionHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание транзакции', params);
    const { biz_id, ...body } = params;
    const response = await finologClient.post(`/v1/biz/${biz_id}/transaction`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create transaction', { error });
    return formatError(error, 'finolog_create_transaction');
  }
};

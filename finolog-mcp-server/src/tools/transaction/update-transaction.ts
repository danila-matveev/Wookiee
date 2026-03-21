import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateTransactionTool: ToolDefinition = {
  name: 'finolog_update_transaction',
  description: 'Обновить транзакцию по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID транзакции',
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
    required: ['biz_id', 'id'],
  },
};

export const updateTransactionHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление транзакции', params);
    const { biz_id, id, ...body } = params;
    const response = await finologClient.put(`/v1/biz/${biz_id}/transaction/${id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update transaction', { error });
    return formatError(error, 'finolog_update_transaction');
  }
};

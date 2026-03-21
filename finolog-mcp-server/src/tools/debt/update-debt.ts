import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateDebtTool: ToolDefinition = {
  name: 'finolog_update_debt',
  description: 'Обновить долг по ID',
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
      debt_id: {
        type: 'number',
        description: 'ID долга',
      },
      value: {
        type: 'number',
        description: 'Сумма долга',
      },
      date: {
        type: 'string',
        description: 'Дата долга (YYYY-MM-DD)',
      },
      type: {
        type: 'string',
        description: 'Тип долга: in или out',
      },
      currency_id: {
        type: 'number',
        description: 'ID валюты',
      },
    },
    required: ['biz_id', 'contractor_id', 'debt_id'],
  },
};

export const updateDebtHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление долга', params);
    const { biz_id, contractor_id, debt_id, ...body } = params as any;
    const response = await finologClient.put(`/v1/biz/${biz_id}/contractor/${contractor_id}/debt/${debt_id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update debt', { error });
    return formatError(error, 'finolog_update_debt');
  }
};

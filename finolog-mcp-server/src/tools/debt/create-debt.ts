import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createDebtTool: ToolDefinition = {
  name: 'finolog_create_debt',
  description: 'Создать долг контрагента',
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
        description: 'Тип долга: in (входящий) или out (исходящий)',
      },
      currency_id: {
        type: 'number',
        description: 'ID валюты',
      },
    },
    required: ['biz_id', 'contractor_id', 'value', 'date', 'type', 'currency_id'],
  },
};

export const createDebtHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание долга', params);
    const { biz_id, contractor_id, ...body } = params as any;
    const response = await finologClient.post(`/v1/biz/${biz_id}/contractor/${contractor_id}/debt`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create debt', { error });
    return formatError(error, 'finolog_create_debt');
  }
};

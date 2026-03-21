import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateAccountTool: ToolDefinition = {
  name: 'finolog_update_account',
  description: 'Обновить счёт по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID счёта',
      },
      name: {
        type: 'string',
        description: 'Название счёта',
      },
      company_id: {
        type: 'number',
        description: 'ID юридического лица',
      },
      currency_id: {
        type: 'number',
        description: 'ID валюты',
      },
      initial_balance: {
        type: 'number',
        description: 'Начальный остаток',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const updateAccountHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление счёта', params);
    const { biz_id, id, ...body } = params;
    const response = await finologClient.put(`/v1/biz/${biz_id}/account/${id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update account', { error });
    return formatError(error, 'finolog_update_account');
  }
};

import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createAccountTool: ToolDefinition = {
  name: 'finolog_create_account',
  description: 'Создать новый счёт в бизнесе',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      company_id: {
        type: 'number',
        description: 'ID юридического лица',
      },
      currency_id: {
        type: 'number',
        description: 'ID валюты',
      },
      name: {
        type: 'string',
        description: 'Название счёта',
      },
      initial_balance: {
        type: 'number',
        description: 'Начальный остаток',
      },
    },
    required: ['biz_id', 'company_id', 'currency_id', 'name'],
  },
};

export const createAccountHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание счёта', params);
    const { biz_id, ...body } = params;
    const response = await finologClient.post(`/v1/biz/${biz_id}/account`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create account', { error });
    return formatError(error, 'finolog_create_account');
  }
};

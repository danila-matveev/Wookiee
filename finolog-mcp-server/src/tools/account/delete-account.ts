import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deleteAccountTool: ToolDefinition = {
  name: 'finolog_delete_account',
  description: 'Удалить счёт по ID',
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
    },
    required: ['biz_id', 'id'],
  },
};

export const deleteAccountHandler: ToolHandler = async (params) => {
  try {
    logger.info('Удаление счёта', params);
    const { biz_id, id } = params;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/account/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete account', { error });
    return formatError(error, 'finolog_delete_account');
  }
};

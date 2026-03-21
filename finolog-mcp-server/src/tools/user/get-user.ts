import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getUserTool: ToolDefinition = {
  name: 'finolog_get_user',
  description: 'Получить текущего пользователя',
  inputSchema: {
    type: 'object',
    properties: {},
    required: [],
  },
};

export const getUserHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение текущего пользователя', params);
    const response = await finologClient.get('/v1/user');
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get user', { error });
    return formatError(error, 'finolog_get_user');
  }
};

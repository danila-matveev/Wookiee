import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateUserTool: ToolDefinition = {
  name: 'finolog_update_user',
  description: 'Обновить профиль текущего пользователя',
  inputSchema: {
    type: 'object',
    properties: {
      first_name: { type: 'string', description: 'Имя' },
      last_name: { type: 'string', description: 'Фамилия' },
    },
    required: [],
  },
};

export const updateUserHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление профиля пользователя', params);
    const response = await finologClient.put('/v1/user', params);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update user', { error });
    return formatError(error, 'finolog_update_user');
  }
};

import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createAutoeditorTool: ToolDefinition = {
  name: 'finolog_create_autoeditor',
  description: 'Создать автоправило для контрагента',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID контрагента',
      },
      config: {
        type: 'object',
        description: 'Конфигурация автоправила',
      },
    },
    required: ['biz_id', 'id', 'config'],
  },
};

export const createAutoeditorHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание автоправила для контрагента', params);
    const { biz_id, id, ...body } = params;
    const response = await finologClient.post(`/v1/biz/${biz_id}/contractor/${id}/autoeditor`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create autoeditor', { error });
    return formatError(error, 'finolog_create_autoeditor');
  }
};

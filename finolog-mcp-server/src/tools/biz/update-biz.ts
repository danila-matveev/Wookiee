import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateBizTool: ToolDefinition = {
  name: 'finolog_update_biz',
  description: 'Обновить бизнес по ID',
  inputSchema: {
    type: 'object',
    properties: {
      id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      name: {
        type: 'string',
        description: 'Новое название бизнеса',
      },
    },
    required: ['id'],
  },
};

export const updateBizHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление бизнеса', params);
    const { id, ...body } = params;
    const response = await finologClient.put(`/v1/biz/${id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update business', { error });
    return formatError(error, 'finolog_update_biz');
  }
};

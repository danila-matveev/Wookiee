import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deleteBizTool: ToolDefinition = {
  name: 'finolog_delete_biz',
  description: 'Удалить бизнес по ID',
  inputSchema: {
    type: 'object',
    properties: {
      id: {
        type: 'number',
        description: 'ID бизнеса',
      },
    },
    required: ['id'],
  },
};

export const deleteBizHandler: ToolHandler = async (params) => {
  try {
    logger.info('Удаление бизнеса', params);
    const { id } = params;
    const response = await finologClient.delete(`/v1/biz/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete business', { error });
    return formatError(error, 'finolog_delete_biz');
  }
};

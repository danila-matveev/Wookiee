import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getCategoryTool: ToolDefinition = {
  name: 'finolog_get_category',
  description: 'Получить категорию ДДС по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID категории',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const getCategoryHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение категории', params);
    const { biz_id, id } = params;
    const response = await finologClient.get(`/v1/biz/${biz_id}/category/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get category', { error });
    return formatError(error, 'finolog_get_category');
  }
};

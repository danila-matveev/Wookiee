import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deleteCategoryTool: ToolDefinition = {
  name: 'finolog_delete_category',
  description: 'Удалить категорию ДДС по ID',
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

export const deleteCategoryHandler: ToolHandler = async (params) => {
  try {
    logger.info('Удаление категории', params);
    const { biz_id, id } = params;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/category/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete category', { error });
    return formatError(error, 'finolog_delete_category');
  }
};

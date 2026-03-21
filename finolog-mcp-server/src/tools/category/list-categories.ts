import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listCategoriesTool: ToolDefinition = {
  name: 'finolog_list_categories',
  description: 'Получить список категорий ДДС бизнеса',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
    },
    required: ['biz_id'],
  },
};

export const listCategoriesHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка категорий', params);
    const { biz_id } = params;
    const response = await finologClient.get(`/v1/biz/${biz_id}/category`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list categories', { error });
    return formatError(error, 'finolog_list_categories');
  }
};

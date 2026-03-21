import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateCategoryTool: ToolDefinition = {
  name: 'finolog_update_category',
  description: 'Обновить категорию ДДС по ID',
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
      name: {
        type: 'string',
        description: 'Название категории',
      },
      type: {
        type: 'string',
        description: 'Тип категории: in, out, inout',
      },
      parent_id: {
        type: 'number',
        description: 'ID родительской категории',
      },
      color: {
        type: 'string',
        description: 'Цвет категории',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const updateCategoryHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление категории', params);
    const { biz_id, id, ...body } = params;
    const response = await finologClient.put(`/v1/biz/${biz_id}/category/${id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update category', { error });
    return formatError(error, 'finolog_update_category');
  }
};

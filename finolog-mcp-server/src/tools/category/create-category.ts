import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createCategoryTool: ToolDefinition = {
  name: 'finolog_create_category',
  description: 'Создать категорию ДДС в бизнесе',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
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
    required: ['biz_id', 'name', 'type'],
  },
};

export const createCategoryHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание категории', params);
    const { biz_id, ...body } = params;
    const response = await finologClient.post(`/v1/biz/${biz_id}/category`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create category', { error });
    return formatError(error, 'finolog_create_category');
  }
};

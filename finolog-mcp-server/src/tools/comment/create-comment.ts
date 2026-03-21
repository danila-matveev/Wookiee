import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createCommentTool: ToolDefinition = {
  name: 'finolog_create_comment',
  description: 'Добавить комментарий к объекту',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: { type: 'number', description: 'ID бизнеса' },
      model_type: { type: 'string', description: 'Тип модели' },
      model_id: { type: 'number', description: 'ID модели' },
      text: { type: 'string', description: 'Текст комментария' },
      files: { type: 'array', description: 'Прикреплённые файлы', items: { type: 'string' } },
    },
    required: ['biz_id', 'model_type', 'model_id', 'text'],
  },
};

export const createCommentHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание комментария', params);
    const { biz_id, ...body } = params;
    const response = await finologClient.post(`/v1/biz/${biz_id}/comment`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create comment', { error });
    return formatError(error, 'finolog_create_comment');
  }
};

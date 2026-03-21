import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listCommentsTool: ToolDefinition = {
  name: 'finolog_list_comments',
  description: 'Получить список комментариев',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: { type: 'number', description: 'ID бизнеса' },
      model_type: { type: 'string', description: 'Тип модели' },
      model_id: { type: 'number', description: 'ID модели' },
      type: { type: 'string', description: 'Тип комментария' },
      page: { type: 'number', description: 'Номер страницы' },
      per_page: { type: 'number', description: 'Количество на странице' },
    },
    required: ['biz_id'],
  },
};

export const listCommentsHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка комментариев', params);
    const { biz_id, ...query } = params;
    const queryString = Object.entries(query)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
      .join('&');
    const url = `/v1/biz/${biz_id}/comment${queryString ? `?${queryString}` : ''}`;
    const response = await finologClient.get(url);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list comments', { error });
    return formatError(error, 'finolog_list_comments');
  }
};

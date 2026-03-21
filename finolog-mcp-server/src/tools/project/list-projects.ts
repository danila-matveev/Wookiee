import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listProjectsTool: ToolDefinition = {
  name: 'finolog_list_projects',
  description: 'Получить список проектов бизнеса',
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

export const listProjectsHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка проектов', params);
    const { biz_id } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/project`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list projects', { error });
    return formatError(error, 'finolog_list_projects');
  }
};

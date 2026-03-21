import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deleteCompanyTool: ToolDefinition = {
  name: 'finolog_delete_company',
  description: 'Удалить юридическое лицо по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID юр. лица',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const deleteCompanyHandler: ToolHandler = async (params) => {
  try {
    logger.info('Удаление юр. лица', params);
    const { biz_id, id } = params;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/company/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete company', { error });
    return formatError(error, 'finolog_delete_company');
  }
};

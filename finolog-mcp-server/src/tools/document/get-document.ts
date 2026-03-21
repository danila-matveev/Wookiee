import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getDocumentTool: ToolDefinition = {
  name: 'finolog_get_document',
  description: 'Получить документ по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID документа',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const getDocumentHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение документа', params);
    const { biz_id, id } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/orders/document/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get document', { error });
    return formatError(error, 'finolog_get_document');
  }
};

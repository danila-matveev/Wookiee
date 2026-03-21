import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deleteDocumentTool: ToolDefinition = {
  name: 'finolog_delete_document',
  description: 'Удалить документ по ID',
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

export const deleteDocumentHandler: ToolHandler = async (params) => {
  try {
    logger.info('Удаление документа', params);
    const { biz_id, id } = params as any;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/orders/document/${id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete document', { error });
    return formatError(error, 'finolog_delete_document');
  }
};

import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const getDocumentPdfTool: ToolDefinition = {
  name: 'finolog_get_document_pdf',
  description: 'Получить PDF документа (счёт)',
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
      no_sign: {
        type: 'boolean',
        description: 'Без подписи и печати',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const getDocumentPdfHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение PDF документа', params);
    const { biz_id, id, ...query } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/orders/document/${id}/pdf/invoice`, query);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to get document PDF', { error });
    return formatError(error, 'finolog_get_document_pdf');
  }
};

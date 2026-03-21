import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listDocumentsTool: ToolDefinition = {
  name: 'finolog_list_documents',
  description: 'Получить список документов бизнеса',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      kind: {
        type: 'string',
        description: 'Тип документа: invoice или shipment',
      },
      template: {
        type: 'string',
        description: 'Шаблон документа',
      },
      page: {
        type: 'number',
        description: 'Номер страницы',
      },
      per_page: {
        type: 'number',
        description: 'Количество на странице',
      },
    },
    required: ['biz_id'],
  },
};

export const listDocumentsHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка документов', params);
    const { biz_id, ...query } = params as any;
    const response = await finologClient.get(`/v1/biz/${biz_id}/orders/document`, query);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list documents', { error });
    return formatError(error, 'finolog_list_documents');
  }
};

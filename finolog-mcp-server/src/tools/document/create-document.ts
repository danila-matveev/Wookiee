import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createDocumentTool: ToolDefinition = {
  name: 'finolog_create_document',
  description: 'Создать документ в бизнесе',
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
      vat_type: {
        type: 'string',
        description: 'Тип НДС',
      },
      contractors: {
        type: 'array',
        description: 'Массив контрагентов',
      },
      items: {
        type: 'array',
        description: 'Массив товаров/услуг',
      },
    },
    required: ['biz_id', 'kind'],
  },
};

export const createDocumentHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание документа', params);
    const { biz_id, ...body } = params as any;
    const response = await finologClient.post(`/v1/biz/${biz_id}/orders/document`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create document', { error });
    return formatError(error, 'finolog_create_document');
  }
};

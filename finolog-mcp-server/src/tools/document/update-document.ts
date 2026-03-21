import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateDocumentTool: ToolDefinition = {
  name: 'finolog_update_document',
  description: 'Обновить документ по ID',
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
    required: ['biz_id', 'id'],
  },
};

export const updateDocumentHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление документа', params);
    const { biz_id, id, ...body } = params as any;
    const response = await finologClient.put(`/v1/biz/${biz_id}/orders/document/${id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update document', { error });
    return formatError(error, 'finolog_update_document');
  }
};

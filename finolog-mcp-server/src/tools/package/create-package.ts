import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createPackageTool: ToolDefinition = {
  name: 'finolog_create_package',
  description: 'Создать пакет в заказе',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: { type: 'number', description: 'ID бизнеса' },
      vat_type: { type: 'string', description: 'Тип НДС' },
    },
    required: ['biz_id'],
  },
};

export const createPackageHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание пакета', params);
    const { biz_id, ...body } = params;
    const response = await finologClient.post(`/v1/biz/${biz_id}/orders/package`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create package', { error });
    return formatError(error, 'finolog_create_package');
  }
};

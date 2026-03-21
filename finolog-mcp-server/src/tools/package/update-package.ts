import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updatePackageTool: ToolDefinition = {
  name: 'finolog_update_package',
  description: 'Обновить пакет в заказе',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: { type: 'number', description: 'ID бизнеса' },
      package_id: { type: 'number', description: 'ID пакета' },
      vat_type: { type: 'string', description: 'Тип НДС' },
    },
    required: ['biz_id', 'package_id'],
  },
};

export const updatePackageHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление пакета', params);
    const { biz_id, package_id, ...body } = params;
    const response = await finologClient.put(`/v1/biz/${biz_id}/orders/package/${package_id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update package', { error });
    return formatError(error, 'finolog_update_package');
  }
};

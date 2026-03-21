import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const deletePackageTool: ToolDefinition = {
  name: 'finolog_delete_package',
  description: 'Удалить пакет из заказа',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: { type: 'number', description: 'ID бизнеса' },
      package_id: { type: 'number', description: 'ID пакета' },
    },
    required: ['biz_id', 'package_id'],
  },
};

export const deletePackageHandler: ToolHandler = async (params) => {
  try {
    logger.info('Удаление пакета', params);
    const { biz_id, package_id } = params;
    const response = await finologClient.delete(`/v1/biz/${biz_id}/orders/package/${package_id}`);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to delete package', { error });
    return formatError(error, 'finolog_delete_package');
  }
};

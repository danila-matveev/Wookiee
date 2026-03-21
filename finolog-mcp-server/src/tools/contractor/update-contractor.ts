import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateContractorTool: ToolDefinition = {
  name: 'finolog_update_contractor',
  description: 'Обновить контрагента по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID контрагента',
      },
      name: {
        type: 'string',
        description: 'Название контрагента',
      },
      email: {
        type: 'string',
        description: 'Email контрагента',
      },
      phone: {
        type: 'string',
        description: 'Телефон контрагента',
      },
      person: {
        type: 'string',
        description: 'Контактное лицо',
      },
      description: {
        type: 'string',
        description: 'Описание контрагента',
      },
    },
    required: ['biz_id', 'id'],
  },
};

export const updateContractorHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление контрагента', params);
    const { biz_id, id, ...body } = params;
    const response = await finologClient.put(`/v1/biz/${biz_id}/contractor/${id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update contractor', { error });
    return formatError(error, 'finolog_update_contractor');
  }
};

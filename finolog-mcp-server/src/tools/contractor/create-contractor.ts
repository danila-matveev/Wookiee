import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createContractorTool: ToolDefinition = {
  name: 'finolog_create_contractor',
  description: 'Создать контрагента в бизнесе',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
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
    required: ['biz_id', 'name'],
  },
};

export const createContractorHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание контрагента', params);
    const { biz_id, ...body } = params;
    const response = await finologClient.post(`/v1/biz/${biz_id}/contractor`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create contractor', { error });
    return formatError(error, 'finolog_create_contractor');
  }
};

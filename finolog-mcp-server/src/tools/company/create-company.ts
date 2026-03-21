import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createCompanyTool: ToolDefinition = {
  name: 'finolog_create_company',
  description: 'Создать юридическое лицо в бизнесе',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      name: {
        type: 'string',
        description: 'Краткое название',
      },
      full_name: {
        type: 'string',
        description: 'Полное название',
      },
      phone: {
        type: 'string',
        description: 'Телефон',
      },
      web: {
        type: 'string',
        description: 'Веб-сайт',
      },
      address: {
        type: 'string',
        description: 'Адрес',
      },
    },
    required: ['biz_id', 'name'],
  },
};

export const createCompanyHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание юр. лица', params);
    const { biz_id, ...body } = params;
    const response = await finologClient.post(`/v1/biz/${biz_id}/company`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create company', { error });
    return formatError(error, 'finolog_create_company');
  }
};

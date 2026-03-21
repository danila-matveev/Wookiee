import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateCompanyTool: ToolDefinition = {
  name: 'finolog_update_company',
  description: 'Обновить юридическое лицо по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID юр. лица',
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
    required: ['biz_id', 'id'],
  },
};

export const updateCompanyHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление юр. лица', params);
    const { biz_id, id, ...body } = params;
    const response = await finologClient.put(`/v1/biz/${biz_id}/company/${id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update company', { error });
    return formatError(error, 'finolog_update_company');
  }
};

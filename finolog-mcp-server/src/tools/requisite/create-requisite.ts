import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const createRequisiteTool: ToolDefinition = {
  name: 'finolog_create_requisite',
  description: 'Создать реквизиты контрагента',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      contractor_id: {
        type: 'number',
        description: 'ID контрагента',
      },
      name: {
        type: 'string',
        description: 'Название реквизитов',
      },
      bank_name: {
        type: 'string',
        description: 'Название банка',
      },
      bank_bik: {
        type: 'string',
        description: 'БИК банка',
      },
      bank_account: {
        type: 'string',
        description: 'Расчётный счёт',
      },
      corr_account: {
        type: 'string',
        description: 'Корреспондентский счёт',
      },
      inn: {
        type: 'string',
        description: 'ИНН',
      },
      kpp: {
        type: 'string',
        description: 'КПП',
      },
      ogrn: {
        type: 'string',
        description: 'ОГРН',
      },
      address: {
        type: 'string',
        description: 'Адрес',
      },
    },
    required: ['biz_id', 'contractor_id', 'name'],
  },
};

export const createRequisiteHandler: ToolHandler = async (params) => {
  try {
    logger.info('Создание реквизитов', params);
    const { biz_id, ...body } = params as any;
    const response = await finologClient.post(`/v1/biz/${biz_id}/requisite`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to create requisite', { error });
    return formatError(error, 'finolog_create_requisite');
  }
};

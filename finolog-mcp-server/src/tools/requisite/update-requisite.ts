import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const updateRequisiteTool: ToolDefinition = {
  name: 'finolog_update_requisite',
  description: 'Обновить реквизиты по ID',
  inputSchema: {
    type: 'object',
    properties: {
      biz_id: {
        type: 'number',
        description: 'ID бизнеса',
      },
      id: {
        type: 'number',
        description: 'ID реквизитов',
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
    required: ['biz_id', 'id'],
  },
};

export const updateRequisiteHandler: ToolHandler = async (params) => {
  try {
    logger.info('Обновление реквизитов', params);
    const { biz_id, id, ...body } = params as any;
    const response = await finologClient.put(`/v1/biz/${biz_id}/requisite/${id}`, body);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to update requisite', { error });
    return formatError(error, 'finolog_update_requisite');
  }
};

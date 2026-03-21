import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listCurrenciesTool: ToolDefinition = {
  name: 'finolog_list_currencies',
  description: 'Получить список валют',
  inputSchema: {
    type: 'object',
    properties: {},
    required: [],
  },
};

export const listCurrenciesHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка валют', params);
    const response = await finologClient.get('/v1/currency');
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list currencies', { error });
    return formatError(error, 'finolog_list_currencies');
  }
};

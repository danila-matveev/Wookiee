import { finologClient } from '../../client/finolog-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const listUnitsTool: ToolDefinition = {
  name: 'finolog_list_units',
  description: 'Получить список единиц измерения',
  inputSchema: {
    type: 'object',
    properties: {},
    required: [],
  },
};

export const listUnitsHandler: ToolHandler = async (params) => {
  try {
    logger.info('Получение списка единиц измерения', params);
    const response = await finologClient.get('/v1/unit');
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list units', { error });
    return formatError(error, 'finolog_list_units');
  }
};

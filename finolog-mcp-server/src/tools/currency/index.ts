import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listCurrenciesTool, listCurrenciesHandler } from './list-currencies.js';

export const currencyTools: ToolDefinition[] = [
  listCurrenciesTool,
];

export const currencyHandlers: Record<string, ToolHandler> = {
  [listCurrenciesTool.name]: listCurrenciesHandler,
};

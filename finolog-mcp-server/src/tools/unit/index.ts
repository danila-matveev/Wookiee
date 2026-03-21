import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { listUnitsTool, listUnitsHandler } from './list-units.js';

export const unitTools: ToolDefinition[] = [
  listUnitsTool,
];

export const unitHandlers: Record<string, ToolHandler> = {
  [listUnitsTool.name]: listUnitsHandler,
};

#!/usr/bin/env node

/**
 * Точка входа MCP сервера для Finolog API.
 * Поддерживает два транспорта: stdio (default) и HTTP (MCP_TRANSPORT=http).
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { createServer, IncomingMessage, ServerResponse } from 'node:http';

import { allTools, getHandler } from './tools/index.js';
import { logger } from './utils/logger.js';
import { config } from './config/config.js';

function createMcpServer(): Server {
  const server = new Server(
    { name: 'finolog-mcp-server', version: '0.1.0' },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    logger.debug('Listing tools', { count: allTools.length });
    return {
      tools: allTools.map((tool) => ({
        name: tool.name,
        description: tool.description,
        inputSchema: tool.inputSchema,
      })),
    };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request: any): Promise<any> => {
    const { name, arguments: args } = request.params;
    logger.info('Tool called', { name, args });

    try {
      const handler = getHandler(name);
      if (!handler) {
        const errorMsg = `Unknown tool: ${name}`;
        logger.error(errorMsg);
        return {
          content: [{ type: 'text' as const, text: JSON.stringify({ error: errorMsg }, null, 2) }],
          isError: true,
        };
      }

      const result = await handler(args || {});
      logger.info('Tool executed successfully', { name });
      return result;
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      logger.error('Tool execution failed', { name, error: errorMsg });
      return {
        content: [{ type: 'text' as const, text: JSON.stringify({ error: errorMsg, tool: name }, null, 2) }],
        isError: true,
      };
    }
  });

  return server;
}

async function startStdio() {
  const server = createMcpServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);

  logger.info('Finolog MCP Server started (stdio)', { toolsCount: allTools.length });

  const signals: NodeJS.Signals[] = ['SIGINT', 'SIGTERM', 'SIGQUIT'];
  signals.forEach((signal) => {
    process.on(signal, async () => {
      logger.info('Shutting down', { signal });
      await server.close();
      process.exit(0);
    });
  });
}

async function startHttp() {
  const port = parseInt(process.env['MCP_PORT'] || '8081', 10);

  const httpServer = createServer(async (req: IncomingMessage, res: ServerResponse) => {
    const url = req.url || '/';

    if (url === '/health' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', service: 'finolog-mcp' }));
      return;
    }

    if (url === '/mcp' || url === '/mcp/') {
      const server = createMcpServer();
      const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
      await server.connect(transport);
      await transport.handleRequest(req, res);
      return;
    }

    res.writeHead(404);
    res.end('Not Found');
  });

  httpServer.listen(port, '0.0.0.0', () => {
    logger.info(`Finolog MCP Server started (HTTP) on port ${port}`, { toolsCount: allTools.length });
  });

  const signals: NodeJS.Signals[] = ['SIGINT', 'SIGTERM', 'SIGQUIT'];
  signals.forEach((signal) => {
    process.on(signal, () => {
      logger.info('Shutting down', { signal });
      httpServer.close();
      process.exit(0);
    });
  });
}

async function main() {
  try {
    logger.info('Starting Finolog MCP Server', {
      version: '0.1.0',
      nodeEnv: config.nodeEnv,
      transport: process.env['MCP_TRANSPORT'] || 'stdio',
    });

    if (process.env['MCP_TRANSPORT'] === 'http') {
      await startHttp();
    } else {
      await startStdio();
    }
  } catch (error) {
    logger.error('Failed to start MCP Server', { error });
    process.exit(1);
  }
}

main().catch((error) => {
  logger.error('Unhandled error in main', { error });
  process.exit(1);
});

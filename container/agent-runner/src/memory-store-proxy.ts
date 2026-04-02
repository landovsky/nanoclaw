/**
 * stdio-to-HTTP MCP proxy for memory-store.
 *
 * Claude Agent SDK v2.1.x doesn't reliably connect to HTTP MCP servers.
 * This proxy bridges stdio (which the SDK handles well) to the streamable
 * HTTP MCP endpoint on the host.
 *
 * Uses @modelcontextprotocol/sdk (already in container dependencies).
 */

// Disable proxy for local MCP connections — OneCLI proxy interferes with fetch()
delete process.env.HTTP_PROXY;
delete process.env.HTTPS_PROXY;
delete process.env.http_proxy;
delete process.env.https_proxy;
process.env.NODE_USE_ENV_PROXY = '0';
process.env.NO_PROXY = '*';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ListPromptsRequestSchema,
  ReadResourceRequestSchema,
  GetPromptRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

const MCP_URL = process.env.MEMORY_STORE_URL || 'http://host.docker.internal:8051/mcp';

// --- group_id validation ---
// Prevent cross-contamination: write operations must target the correct group.
// Read operations (search_nodes, search_memory_facts, get_*) are unrestricted.
// The "global" group is always writable by any agent.
// Main/slack_main agents are unrestricted (they orchestrate across all groups).

const WRITE_TOOLS = new Set(['add_memory', 'delete_episode', 'delete_entity_edge', 'clear_graph']);

const GROUP_FOLDER = process.env.NANOCLAW_GROUP_FOLDER ?? '';
const UNRESTRICTED_FOLDERS = new Set(['main', 'slack_main']);

/** Map group folder to its allowed write group_ids */
function getAllowedWriteGroups(folder: string): Set<string> | null {
  if (UNRESTRICTED_FOLDERS.has(folder)) return null; // null = no restriction
  // Each domain folder can write to its own group_id + global
  return new Set([folder, 'global']);
}

const ALLOWED_WRITE_GROUPS = getAllowedWriteGroups(GROUP_FOLDER);

function validateGroupId(toolName: string, groupId: unknown): string | null {
  if (!WRITE_TOOLS.has(toolName)) return null; // reads are unrestricted
  if (ALLOWED_WRITE_GROUPS === null) return null; // main/slack_main are unrestricted
  if (typeof groupId !== 'string' || groupId === '') return null; // no group_id = default, allow
  if (ALLOWED_WRITE_GROUPS.has(groupId)) return null; // allowed
  return `group_id "${groupId}" is not allowed for folder "${GROUP_FOLDER}". Allowed: ${[...ALLOWED_WRITE_GROUPS].join(', ')}`;
}

async function main() {
  // Connect to the remote HTTP MCP server as a client
  const transport = new StreamableHTTPClientTransport(new URL(MCP_URL));
  const client = new Client({ name: 'memory-store-proxy', version: '1.0.0' });
  await client.connect(transport);

  // Create a local stdio MCP server that proxies all requests
  const server = new Server(
    { name: 'memory-store', version: '1.0.0' },
    { capabilities: { tools: {}, resources: {}, prompts: {} } },
  );

  // Proxy tools/list
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    const result = await client.listTools();
    return { tools: result.tools };
  });

  // Proxy tools/call
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const args = request.params.arguments as Record<string, unknown> | undefined;

    // Log every memory-store tool call to stderr (captured by container runner)
    const logEntry = {
      ts: new Date().toISOString(),
      tool: request.params.name,
      group_id: args?.group_id ?? null,
      query: typeof args?.query === 'string' ? args.query.slice(0, 200) : null,
      session: process.env.NANOCLAW_SESSION_ID ?? null,
      group_folder: process.env.NANOCLAW_GROUP_FOLDER ?? null,
    };
    process.stderr.write(`[memory-store-proxy] ${JSON.stringify(logEntry)}\n`);

    // Validate group_id on write operations
    const violation = validateGroupId(request.params.name, args?.group_id);
    if (violation) {
      process.stderr.write(`[memory-store-proxy] BLOCKED: ${violation}\n`);
      return {
        content: [{ type: 'text', text: `Blocked: ${violation}` }],
        isError: true,
      };
    }

    const result = await client.callTool({
      name: request.params.name,
      arguments: request.params.arguments,
    });
    return { content: result.content, isError: result.isError };
  });

  // Proxy resources/list
  server.setRequestHandler(ListResourcesRequestSchema, async () => {
    try {
      const result = await client.listResources();
      return { resources: result.resources };
    } catch {
      return { resources: [] };
    }
  });

  // Proxy resources/read
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const result = await client.readResource({ uri: request.params.uri });
    return { contents: result.contents };
  });

  // Proxy prompts/list
  server.setRequestHandler(ListPromptsRequestSchema, async () => {
    try {
      const result = await client.listPrompts();
      return { prompts: result.prompts };
    } catch {
      return { prompts: [] };
    }
  });

  // Proxy prompts/get
  server.setRequestHandler(GetPromptRequestSchema, async (request) => {
    const result = await client.getPrompt({
      name: request.params.name,
      arguments: request.params.arguments,
    });
    return { messages: result.messages };
  });

  // Start the stdio server
  const stdioTransport = new StdioServerTransport();
  await server.connect(stdioTransport);
}

main().catch((err) => {
  process.stderr.write(`memory-store-proxy fatal: ${err}\n`);
  process.exit(1);
});

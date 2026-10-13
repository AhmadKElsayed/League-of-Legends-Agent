import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  CompleteRequestSchema,
  GetPromptRequestSchema,
  ListPromptsRequestSchema,
  ListResourcesRequestSchema,
  ListResourceTemplatesRequestSchema,
  ListToolsRequestSchema,
  ListToolsResultSchema,
  LoggingMessageNotificationSchema,
  ReadResourceRequestSchema,
  SubscribeRequestSchema,
  UnsubscribeRequestSchema,
  ResourceUpdatedNotificationSchema,
  ServerCapabilities,
} from "@modelcontextprotocol/sdk/types.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { z } from "zod";

/**
 * tools/list, with per-tool validation relaxed.
 *
 * The OP.GG API returns tools whose `outputSchema.type` is not the literal
 * "object" that the SDK's ListToolsResultSchema requires (outputSchema became
 * a validated field in the 2025-06-18 spec, enforced from SDK 1.17 onward), so
 * `client.listTools()` throws before we ever see the payload. This keeps the
 * result envelope validated and only loosens the individual tool entries, which
 * are stripped of outputSchema below.
 */
const LooseListToolsResultSchema = ListToolsResultSchema.extend({
  tools: z.array(z.any()),
});

export const proxyServer = async ({
  server,
  client,
  serverCapabilities,
}: {
  server: Server;
  client: Client;
  serverCapabilities: ServerCapabilities;
}) => {
  if (serverCapabilities?.logging) {
    server.setNotificationHandler(
      LoggingMessageNotificationSchema,
      async (args) => {
        return client.notification(args);
      },
    );
  }

  if (serverCapabilities?.prompts) {
    server.setRequestHandler(GetPromptRequestSchema, async (args) => {
      return client.getPrompt(args.params);
    });

    server.setRequestHandler(ListPromptsRequestSchema, async (args) => {
      return client.listPrompts(args.params);
    });
  }

  if (serverCapabilities?.resources) {
    server.setRequestHandler(ListResourcesRequestSchema, async (args) => {
      return client.listResources(args.params);
    });

    server.setRequestHandler(
      ListResourceTemplatesRequestSchema,
      async (args) => {
        return client.listResourceTemplates(args.params);
      },
    );

    server.setRequestHandler(ReadResourceRequestSchema, async (args) => {
      return client.readResource(args.params);
    });

    if (serverCapabilities?.resources.subscribe) {
      server.setNotificationHandler(
          ResourceUpdatedNotificationSchema,
          async (args) => {
            return client.notification(args);
          },
      );

      server.setRequestHandler(SubscribeRequestSchema, async (args) => {
        return client.subscribeResource(args.params);
      });

      server.setRequestHandler(UnsubscribeRequestSchema, async (args) => {
        return client.unsubscribeResource(args.params);
      });
    }
  }

  if (serverCapabilities?.tools) {
    server.setRequestHandler(CallToolRequestSchema, async (args) => {
      return client.callTool(args.params);
    });

    server.setRequestHandler(ListToolsRequestSchema, async (args) => {
      const response = await client.request(
        { method: "tools/list", params: args.params },
        LooseListToolsResultSchema
      );
      // Drop the field the downstream client would reject for the same reason.
      for (const tool of response.tools) {
        if (tool && 'outputSchema' in tool) {
          delete tool.outputSchema;
        }
      }
      return response;
    });
  }

  // server.setRequestHandler(CompleteRequestSchema, async (args) => {
  //   return client.complete(args.params);
  // });
};

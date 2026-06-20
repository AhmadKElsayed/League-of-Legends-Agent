import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  CompleteRequestSchema,
  GetPromptRequestSchema,
  ListPromptsRequestSchema,
  ListResourcesRequestSchema,
  ListResourceTemplatesRequestSchema,
  ListToolsRequestSchema,
  LoggingMessageNotificationSchema,
  ReadResourceRequestSchema,
  SubscribeRequestSchema,
  UnsubscribeRequestSchema,
  ResourceUpdatedNotificationSchema,
  ServerCapabilities,
} from "@modelcontextprotocol/sdk/types.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";

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
      // Bypass Zod validation by using a dummy schema
      const anySchema = {
        _def: {},
        parse: (data: any) => data,
        safeParse: (data: any) => ({ success: true, data })
      } as any;
      const response = await client.request(
        { method: "tools/list", params: args.params },
        anySchema
      ) as any;
      if (response && response.tools) {
        for (const tool of response.tools) {
          if ('outputSchema' in tool) {
            delete (tool as any).outputSchema;
          }
        }
      }
      return response;
    });
  }

  // server.setRequestHandler(CompleteRequestSchema, async (args) => {
  //   return client.complete(args.params);
  // });
};

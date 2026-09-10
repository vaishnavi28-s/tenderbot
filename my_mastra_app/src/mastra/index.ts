import { Mastra } from '@mastra/core';
import { LibSQLStore } from '@mastra/libsql';
import { Observability } from '@mastra/observability';
import { LangSmithExporter } from '@mastra/langsmith';
import { scoutAgent, enrichAgent } from './agents/scout';
//console.log('DEBUG - LANGSMITH_API_KEY at Observability construction:', !!process.env.LANGSMITH_API_KEY);
const observability = new Observability({
  configs: {
    langsmith: {
      serviceName: 'tenderbot-mastra',
      exporters: [
        new LangSmithExporter({
          apiKey: process.env.LANGSMITH_API_KEY,
        }),
      ],
    },
  },
});

export const mastra = new Mastra({
  agents: { scoutAgent, enrichAgent },

  storage: new LibSQLStore({
    id: 'tenderbot-mastra-storage',
    url: 'file:./mastra.db',
  }),

  observability,
});
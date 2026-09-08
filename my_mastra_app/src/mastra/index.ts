import { Mastra } from '@mastra/core';
import { scoutAgent, enrichAgent } from './agents/scout';

export const mastra = new Mastra({
  agents: { scoutAgent, enrichAgent },
});

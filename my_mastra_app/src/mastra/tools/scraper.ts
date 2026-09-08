import { createTool } from '@mastra/core/tools';
import { z } from 'zod';

export const scraperTool = createTool({
  id: 'web-scraper',
  description: 'Scrapes the text content of a URL to find tender details.',
  inputSchema: z.object({
    url: z.string().url().describe('The URL of the tender page or notice to analyze'),
  }),
  outputSchema: z.object({
    rawText: z.string(),
  }),
  execute: async ({ url }) => { 
    console.log(`Scraping: ${url}...`);

    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000); // 45 seconds

    try {
      const response = await fetch(url, { 
        signal: controller.signal,
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TenderBotBot/1.0' }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const html = await response.text();
      
      
      const cleanText = html
        .replace(/<script\b[^>]*>([\s\S]*?)<\/script>/gmi, '')
        .replace(/<style\b[^>]*>([\s\S]*?)<\/style>/gmi, '')
        .replace(/<[^>]*>?/gm, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .substring(0, 12000);
      
      return { rawText: cleanText || "Error: Website was reached but no text was found." };

    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.error(`Scraper timed out for: ${url}`);
        return { rawText: "Error: The website took too long to respond (Timeout)." };
      }
      console.error(`Scraper failed: ${error.message}`);
      return { rawText: `Error: Could not fetch content. ${error.message}` };
    } finally {
      clearTimeout(timeoutId);
    }
  },
});

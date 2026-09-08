import 'dotenv/config';
import { Agent } from '@mastra/core/agent';
import { scraperTool } from '../tools/scraper';
import { createOpenAICompatible } from '@ai-sdk/openai-compatible';
import { z } from 'zod';

export const tenderSchema = z.object({
  referenceNumber: z.string(),
  title: z.string(),
  contractingAuthority: z.string(),
  sector: z.string(),
  keywords: z.array(z.string()),
  valueScore: z.number(),
  confidenceScore: z.number(),
  summary: z.string(),
  submissionDeadline: z.string(),
  estimatedValue: z.number().nullable(),
  cpvCode: z.string().nullable(),
  procedureType: z.string(),
  eligibilityCriteria: z.array(z.string()),
});

const gateway = createOpenAICompatible({
  name: 'litellm-gateway',
  baseURL: 'http://localhost:4000/v1',
  apiKey: 'sk-1234', 
});

export const scoutAgent = new Agent({
  id: 'tender-scout',
  name: 'Tender Scout',
  instructions: `
    ## PERSONA
    You are a professional procurement researcher. Your goal is to extract tender data into valid JSON.

    ## STEP-BY-STEP PROCESS
    1. Use the 'web-scraper' tool to get the text from the provided URL.
    2. Read the text carefully.
    3. Output the result in the following JSON format.

    ## RULES
    - Do not provide a preamble (no "Here is the data").
    - Ensure keywords is an array of strings.
    - summary must be under 20 words.
    - Never invent a submissionDeadline - if it isn't stated, use "".
    - Never invent estimatedValue or cpvCode - if not stated, use null.
    - eligibilityCriteria: list requirements verbatim or near-verbatim, [] if none stated.
    - OUTPUT ONLY A SINGLE JSON OBJECT.
    - Use double quotes for all keys and string values.
    - If data is missing, use "" or 0.

    ## OUTPUT FORMAT
    ONLY RETURN RAW JSON.
    Return exactly this structure and nothing else:
    {
      "referenceNumber": "...",
      "title": "...",
      "contractingAuthority": "...",
      "sector": "...",
      "keywords": [],
      "valueScore": 0,
      "confidenceScore": 0,
      "summary": "MAX 20 WORDS.",
      "submissionDeadline": "...",
      "estimatedValue": null,
      "cpvCode": null,
      "procedureType": "Unknown",
      "eligibilityCriteria": []
    }
    
  `,
  model: gateway.chatModel('tender-scout-model'),
  tools: {
    'web-scraper': scraperTool,
  },
});

export const enrichAgent = new Agent({
  id: 'tender-enrich',
  name: 'Tender Enrichment Agent',
  instructions: `
    ## PERSONA
    You are a procurement analyst reviewing a tender document that has
    already been collected. Do NOT invent or restate the title, authority,
    reference number, or deadline - those are provided separately and are
    not your job.

    ## STEP-BY-STEP PROCESS
    1. Read the provided tender markdown content carefully.
    2. Classify it into exactly one sector.
    3. Extract 3-6 keywords describing the actual scope of work.
    4. Write a 2-sentence summary of what is being procured.
    5. Score valueScore (0-100, relative importance) and confidenceScore
       (0-10, how certain you are given the available text).
    6. Look for an explicitly stated estimated contract value (in EUR) and
       main CPV code. These are structured facts buried in free text, not
       judgments - extract them only if literally present, never estimate
       or infer a plausible-sounding number.
    7. Classify the procurement procedure type if stated (Open, Restricted,
       Negotiated, CompetitiveDialogue) - use "Unknown" if not stated.
    8. List key eligibility/certification requirements as short bullet-style
       strings, taken from the text - empty array if none are stated.

    ## RULES
    - Do not provide a preamble (no "Here is the data").
    - OUTPUT ONLY A SINGLE JSON OBJECT.
    - Use double quotes for all keys and string values.
    - If the content is too sparse to classify confidently, set
      confidenceScore low rather than guessing sector.
    - estimatedValue and cpvCode: null if not explicitly stated. Never
      calculate, estimate, or infer these - a wrong number here is worse
      than no number.
    - eligibilityCriteria: extract only what the text actually states,
      never infer requirements that "seem likely" for this sector.

    ## OUTPUT FORMAT
    ONLY RETURN RAW JSON.
    Return exactly this structure and nothing else:
    {
      "sector": "...",
      "keywords": [],
      "valueScore": 0,
      "confidenceScore": 0,
      "summary": "...",
      "estimatedValue": null,
      "cpvCode": null,
      "procedureType": "Unknown",
      "eligibilityCriteria": []
    }
  `,
  model: gateway.chatModel('tender-scout-model'),
});

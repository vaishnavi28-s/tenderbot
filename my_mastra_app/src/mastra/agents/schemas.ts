import { z } from 'zod';

export const TenderDossierSchema = z.object({
  referenceNumber: z.string().nullable(),
  title: z.string(),
  sourceUrl: z.string(),
  contractingAuthority: z.string().max(200).nullable().describe("The buyer/authority running this tender"),
  sector: z.enum(["IT", "Construction", "Healthcare", "Consulting", "Logistics", "Other"]),
  keywords: z.array(z.string()).max(8).nullable().describe("Tags like 'cloud migration', 'GDPR', 'civil works'"),
  valueScore: z.number().min(0).max(100).nullable().describe("Relative estimated value/importance (0-100 scale)"),
  confidenceScore: z.number().min(0).max(10).nullable().describe("AI's certainty based on available data (0-10 scale)"),
  summary: z.string().max(400).nullable().describe("A 2-sentence executive summary for the dashboard"),
  submissionDeadline: z.string().nullable(),
  estimatedValue: z.number().nullable().describe("Estimated contract value in EUR, null if not stated"),
  numberOfLots: z.number().nullable().describe("Number of lots the tender is divided into, null if single-lot or unstated"),
  cpvCode: z.string().nullable().describe("Main CPV procurement code, null if not stated"),
  procedureType: z.enum(["Open", "Restricted", "Negotiated", "CompetitiveDialogue", "Unknown"]),
  eligibilityCriteria: z.array(z.string()).max(10).nullable().describe("Key eligibility/certification requirements, empty array if none stated"),
});

export type TenderDossier = z.infer<typeof TenderDossierSchema>;

export const TenderEnrichmentSchema = z.object({
  contractingAuthority: z.string().max(200).nullable().describe("The buyer/authority running this tender"),
  sector: z.enum(["IT", "Construction", "Healthcare", "Consulting", "Logistics", "Other"]),
  keywords: z.array(z.string()).max(8).nullable().describe("Tags like 'cloud migration', 'GDPR', 'civil works'"),
  valueScore: z.number().min(0).max(100).nullable().describe("Relative estimated value/importance (0-100 scale)"),
  confidenceScore: z.number().min(0).max(10).nullable().describe("AI's certainty based on available data (0-10 scale)"),
  summary: z.string().max(400).nullable().describe("A 2-sentence executive summary for the dashboard"),
  estimatedValue: z.number().nullable().describe("Estimated contract value in EUR, exactly as stated in the text - null if not stated, never estimated"),
  numberOfLots: z.number().nullable().describe("Number of lots the tender is divided into, null if single-lot or unstated"),
  cpvCode: z.string().nullable().describe("Main CPV procurement code if explicitly stated, null otherwise"),
  procedureType: z.enum(["Open", "Restricted", "Negotiated", "CompetitiveDialogue", "Unknown"]),
  eligibilityCriteria: z.array(z.string()).max(10).nullable().describe("Key eligibility/certification requirements verbatim or near-verbatim from the text, empty array if none stated"),
});

export type TenderEnrichment = z.infer<typeof TenderEnrichmentSchema>;
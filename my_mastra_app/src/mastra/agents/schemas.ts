import { z } from 'zod';

// This is our 'Tender Dossier' - the strict format our AI must follow.
export const TenderDossierSchema = z.object({
  referenceNumber: z.string().describe("The official tender/notice reference number"),
  title: z.string().describe("Title of the tender or procurement notice"),
  contractingAuthority: z.string().describe("The buyer/authority running this tender"),
  sector: z.enum(["IT", "Construction", "Healthcare", "Consulting", "Logistics", "Other"]),
  keywords: z.array(z.string()).describe("Tags like 'cloud migration', 'GDPR', 'civil works'"),
  valueScore: z.number().min(0).max(100).describe("Relative estimated value/importance (0-100 scale)"),
  confidenceScore: z.number().min(0).max(10).describe("AI's certainty based on available data (0-10 scale)"),
  summary: z.string().describe("A 2-sentence executive summary for the dashboard"),
  submissionDeadline: z.string().describe("The submission deadline as stated in the source, ISO format if possible"),
  estimatedValue: z.number().nullable().describe("Estimated contract value in EUR, null if not stated"),
  cpvCode: z.string().nullable().describe("Main CPV procurement code, null if not stated"),
  procedureType: z.enum(["Open", "Restricted", "Negotiated", "CompetitiveDialogue", "Unknown"]),
  eligibilityCriteria: z.array(z.string()).describe("Key eligibility/certification requirements, empty array if none stated"),
});

export type TenderDossier = z.infer<typeof TenderDossierSchema>;

export const TenderEnrichmentSchema = z.object({
  sector: z.enum(["IT", "Construction", "Healthcare", "Consulting", "Logistics", "Other"]),
  keywords: z.array(z.string()).describe("Tags like 'cloud migration', 'GDPR', 'civil works'"),
  valueScore: z.number().min(0).max(100).describe("Relative estimated value/importance (0-100 scale)"),
  confidenceScore: z.number().min(0).max(10).describe("AI's certainty based on available data (0-10 scale)"),
  summary: z.string().describe("A 2-sentence executive summary for the dashboard"),
  estimatedValue: z.number().nullable().describe("Estimated contract value in EUR, exactly as stated in the text - null if not stated, never estimated"),
  cpvCode: z.string().nullable().describe("Main CPV procurement code if explicitly stated, null otherwise"),
  procedureType: z.enum(["Open", "Restricted", "Negotiated", "CompetitiveDialogue", "Unknown"]),
  eligibilityCriteria: z.array(z.string()).describe("Key eligibility/certification requirements verbatim or near-verbatim from the text, empty array if none stated"),
});

export type TenderEnrichment = z.infer<typeof TenderEnrichmentSchema>;

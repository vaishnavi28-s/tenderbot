import express from 'express';
import { mastra } from './mastra/index';
import { TenderDossierSchema, TenderEnrichmentSchema } from './mastra/agents/schemas';

const app = express();
app.use(express.json());

function extractJsonObject(text: string): any {
  const start = text.indexOf('{');
  if (start === -1) return null;
  let depth = 0;
  for (let i = start; i < text.length; i++) {
    if (text[i] === '{') depth++;
    if (text[i] === '}') depth--;
    if (depth === 0) {
      const candidate = text.slice(start, i + 1);
      try {
        return JSON.parse(candidate);
      } catch {
        return null;
      }
    }
  }
  return null;
}

const TENDER_SIGNAL_KEYWORDS = [
  "Referenznummer", "Vergabenummer", "Auftraggeber", "Ausschreibungs-ID",
  "CPV-Code", "Angebotsfrist", "Abgabefrist", "Leistungsbeschreibung",
  "Auftragsgegenstand", "Erfüllungsort", "Vergabeart", "Zuschlagskriterien",
  "Bekanntmachung", "Eignungskriterien",
];

function trimMarkdown(raw: string, maxChars = 8000): string {
  if (!raw) return raw;
  const blocks = raw.split(/(?=# Content from )/).filter(b => b.trim());
  if (blocks.length === 0) return raw.slice(0, maxChars);

  const scored = blocks.map(block => {
    const score = TENDER_SIGNAL_KEYWORDS.reduce(
      (sum, kw) => sum + (block.split(kw).length - 1), 0
    );
    return { score, block };
  });
  scored.sort((a, b) => b.score - a.score);

  let result = '';
  for (const { block } of scored) {
    if (result.length + block.length > maxChars) {
      const remaining = maxChars - result.length;
      if (remaining > 200) result += block.slice(0, remaining);
      break;
    }
    result += block;
  }
  return result || raw.slice(0, maxChars);
}

app.post('/enrich-and-store', async (req, res) => {
  const {
    title, link, deadline, city, contracting_authority,
    reference_number, category, markdown
  } = req.body;

  const trimmedMarkdown = trimMarkdown(markdown || '', 8000);

  try {
    console.log(`Mastra is enriching: ${title}`);

    const enrichAgent = mastra.getAgent('enrichAgent');

    let result;
    let lastErr;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        result = await enrichAgent.generate(
          `Here is the collected content for this tender:\n\n${trimmedMarkdown || '(no content collected)'}\n\nExtract the enrichment fields as instructed.`,
          {
            maxSteps: 1,
            modelSettings: {
              maxOutputTokens: 3000,
              temperature: 0,
            }
          }
        );
        break;
      } catch (err) {
        lastErr = err;
        await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
      }
    }
    if (!result) throw lastErr;

    let rawEnrichment: any;
    if (result.text) {
      rawEnrichment = extractJsonObject(result.text);
      if (!rawEnrichment) {
        console.error("Failed to parse enrichment JSON from text block. Raw text:", result.text.slice(0, 500));
      }
    }

    if (!rawEnrichment) {
      throw new Error("Enrichment agent failed to provide a valid JSON object.");
    }

    // Normalize enum fields to a safe fallback instead of hard-failing on near-misses
    const allowedSectors = ["IT", "Construction", "Healthcare", "Consulting", "Logistics", "Other"];
    if (!allowedSectors.includes(rawEnrichment.sector)) {
      console.warn(`Sector "${rawEnrichment.sector}" not in allowed list, using "Other" instead.`);
      rawEnrichment.sector = "Other";
    }

    const allowedProcedureTypes = ["Open", "Restricted", "Negotiated", "CompetitiveDialogue", "Unknown"];
    if (!allowedProcedureTypes.includes(rawEnrichment.procedureType)) {
      console.warn(`ProcedureType "${rawEnrichment.procedureType}" not in allowed list, using "Unknown" instead.`);
      rawEnrichment.procedureType = "Unknown";
    }

    // Quality guard: don't trust self-reported confidence if critical fields are actually empty
    const criticalFields = [
      rawEnrichment.contractingAuthority,
      rawEnrichment.summary,
      rawEnrichment.keywords?.length ? rawEnrichment.keywords : null,
    ].filter(v => v !== null && v !== undefined && v !== "");

    if (criticalFields.length === 0) {
      console.warn(`Low-info extraction for "${title}": 0/3 critical fields populated. Forcing low confidence.`);
      rawEnrichment.confidenceScore = Math.min(rawEnrichment.confidenceScore ?? 0, 2);
    }

    const validatedEnrichment = TenderEnrichmentSchema.parse(rawEnrichment);

    // MERGE: deterministic fields (never touched by the LLM) + LLM enrichment
    const validatedData = TenderDossierSchema.parse({
      referenceNumber: reference_number || null,
      title: title,
      sourceUrl: link,
      contractingAuthority: validatedEnrichment.contractingAuthority || contracting_authority || null,
      submissionDeadline: deadline || null,
      sector: validatedEnrichment.sector,
      keywords: validatedEnrichment.keywords,
      valueScore: validatedEnrichment.valueScore,
      confidenceScore: validatedEnrichment.confidenceScore,
      summary: validatedEnrichment.summary,
      estimatedValue: validatedEnrichment.estimatedValue,
      numberOfLots: validatedEnrichment.numberOfLots,
      cpvCode: validatedEnrichment.cpvCode,
      procedureType: validatedEnrichment.procedureType,
      eligibilityCriteria: validatedEnrichment.eligibilityCriteria,
    });

    console.log("Data validated, sending to Python audit:", validatedData.title);

    const pythonResponse = await fetch('http://localhost:8000/validate-and-store', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...validatedData, category })
    });

    if (!pythonResponse.ok) {
      const errorText = await pythonResponse.text();
      throw new Error(`Python Audit Error: ${errorText}`);
    }

    const finalResult = await pythonResponse.json();
    res.json(finalResult);
    mastra.observability.flush()
      .then(() => console.log('LangSmith flush: SUCCESS'))
      .catch(err => console.error('LangSmith flush FAILED:', err));
  } catch (error: any) {
    console.error('Enrichment Pipeline Error:', error.message);

    if (error.name === 'ZodError') {
      return res.status(422).json({
        error: 'Schema Validation Failed',
        details: error.errors
      });
    }

    res.status(500).json({
      error: 'Processing failed',
      details: error.message
    });
  }
});

const server = app.listen(3000, () => {
  console.log('Mastra Signal Processor on port 3000 ...');
});

server.timeout = 600000;
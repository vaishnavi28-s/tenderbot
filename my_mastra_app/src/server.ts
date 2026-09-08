import express from 'express';
import { mastra } from './mastra/index';
import { tenderSchema } from './mastra/agents/scout';
import { TenderEnrichmentSchema } from './mastra/agents/schemas';

const app = express();
app.use(express.json());


app.post('/enrich-and-store', async (req, res) => {
  const {
    title, link, deadline, city, contracting_authority,
    reference_number, category, markdown
  } = req.body;

  try {
    console.log(`Mastra is enriching: ${title}`);

    const enrichAgent = mastra.getAgent('enrichAgent');

    const result = await enrichAgent.generate(
      `Here is the collected content for this tender:\n\n${markdown || '(no content collected)'}\n\nExtract the enrichment fields as instructed.`,
      {
        maxSteps: 1,
        modelSettings: {
          maxOutputTokens: 800,
          temperature: 0,
        }
      }
    );

    let rawEnrichment: any;
    if (result.text) {
      const jsonMatch = result.text.match(/(\{[\s\S]*?\})/g);
      if (jsonMatch) {
        try {
          rawEnrichment = JSON.parse(jsonMatch[jsonMatch.length - 1]);
        } catch (e) {
          console.error("Failed to parse enrichment JSON from text block");
        }
      }
    }

        if (!rawEnrichment) {
      throw new Error("Enrichment agent failed to provide a valid JSON object.");
    }

    
    const allowedSectors = ["IT", "Construction", "Healthcare", "Consulting", "Logistics", "Other"];
    if (!allowedSectors.includes(rawEnrichment.sector)) {
      console.warn(`Sector "${rawEnrichment.sector}" not in allowed list, using "Other" instead.`);
      rawEnrichment.sector = "Other";
    }

    const validatedEnrichment = TenderEnrichmentSchema.parse(rawEnrichment);

    // MERGE: deterministic fields (never touched by the LLM) + LLM enrichment
    const validatedData = tenderSchema.parse({
      referenceNumber: reference_number || "",
      title: title,
      contractingAuthority: contracting_authority || "",
      submissionDeadline: deadline || "",
      sector: validatedEnrichment.sector,
      keywords: validatedEnrichment.keywords,
      valueScore: validatedEnrichment.valueScore,
      confidenceScore: validatedEnrichment.confidenceScore,
      summary: validatedEnrichment.summary,
      estimatedValue: validatedEnrichment.estimatedValue,
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

app.post('/scout', async (req, res) => {
  const { url } = req.body;
  
  const scout = mastra.getAgent('scoutAgent'); 

  try {
    console.log(`Mastra is scouting: ${url}`);

    const result = await scout.generate(
      `First, use the web-scraper to get content from ${url}. 
       Read the content and extract the tender details.
       Provide the final result as a clean JSON object matching the schema.`, 
      {
        maxSteps: 5,
        modelSettings: {
          maxOutputTokens: 1500,
          temperature: 0,      
        }
      }
    );

    
    let rawData: any;

    if (result.text) {
      console.log("Extracting JSON from agent text...");
      const jsonMatch = result.text.match(/(\{[\s\S]*?\})/g);
      if (jsonMatch) {
        try {
            // We take the last JSON block in case there is reasoning text before it
            rawData = JSON.parse(jsonMatch[jsonMatch.length - 1]);
        } catch (e) {
            console.error("Failed to parse JSON from text block");
        }
      }
    }

    // Fallback: Check toolResults if text was empty or didn't contain JSON
    if (!rawData && result.toolResults && result.toolResults.length > 0) {
      console.log("Checking tool results for data...");
      const lastResult = result.toolResults[result.toolResults.length - 1];
      rawData = (lastResult as any).output;
    }

    // Fallback: Checking if Mastra populated .object anyway
    if (!rawData && (result as any).object) {
      rawData = (result as any).object;
    }

    if (!rawData || typeof rawData !== 'object') {
        console.error("Full Result for Debugging:", JSON.stringify(result, null, 2));
        throw new Error("Agent failed to provide a valid JSON object. Check if the scraper returned enough content.");
    }

    // MANUAL ZOD VALIDATION 
    const validatedData = tenderSchema.parse(rawData);
    
    console.log("Data validated, sending to Python audit:", validatedData.title);

    // PYTHON LAYER HANDOFF
    const pythonResponse = await fetch('http://localhost:8000/validate-and-store', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(validatedData)
    });

    if (!pythonResponse.ok) {
        const errorText = await pythonResponse.text();
        throw new Error(`Python Audit Error: ${errorText}`);
    }

    const finalResult = await pythonResponse.json();
    res.json(finalResult);

  } catch (error: any) {
    console.error('Pipeline Error:', error.message);
    
    // If it's a Zod error, we make the output readable
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

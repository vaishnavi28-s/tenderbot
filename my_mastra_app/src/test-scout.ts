import { scoutAgent } from './mastra/agents/scout';
import { TenderDossierSchema } from './mastra/agents/schemas';

async function runScout() {
  console.log("Scout is analyzing a tender notice...");

  try {

    const result = await scoutAgent.generate(
      "The City of Mannheim is running an open tender (Ref. MA-2026-0417) for cloud infrastructure migration services, estimated value €450,000, submission deadline 15 October 2026."
    );

    const cleanJson = result.text.replace(/```json|```/g, "").trim();

    const rawObject = JSON.parse(cleanJson);


    const validatedData = TenderDossierSchema.parse(rawObject);

    console.log("SUCCESS! Validated Data:");
    console.dir(validatedData, { depth: null });

  } catch (error) {
    console.error("Extraction failed.");
    console.error("AI returned this instead of JSON:", error);
  }
}

runScout();

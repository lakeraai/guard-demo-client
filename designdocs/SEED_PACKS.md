# SEED_PACKS.md
_Last updated: 2025-08-29_

This doc defines the design for **AI-generated Seed Packs** integrated into Task 3 (RAG Processing).

## Purpose
Allow demo users to generate synthetic, industry-specific content on-demand, using their **branding** and **LLM config**, so RAG retrieval has meaningful data without requiring external uploads.

## Modes
### Quick Generate
- One-click, uses existing **Branding** + **LLM** settings:
  - business_name, tagline, hero_text, system_prompt
- Prompt template auto-combines these into a concise seed pack (FAQs, glossary, objections, product blurbs).

### Guided Generate
- Modal with explicit questions:
  - industry (dropdown: FinTech, Retail, Healthcare, SaaS, Cybersecurity, etc.)
  - audience (free text)
  - use_cases[] (multi-select)
  - tone (dropdown: professional, casual, technical, friendly)
  - depth (short, medium, long)
  - include_sections[] (faqs, glossary, policies, objections)
  - constraints (optional text, e.g., "avoid medical advice")
- Returns a markdown preview, editable, then ingested into RAG.

## API Contract
`POST /rag/generate`
- Request (Quick):
```json
{
  "mode": "quick",
  "preview_only": true
}
```
- Request (Guided):
```json
{
  "mode": "guided",
  "industry": "FinTech",
  "seed_prompt": "Produce a concise knowledge pack...",
  "options": {
    "tone": "professional",
    "depth": "medium",
    "include_sections": ["faqs","glossary","objections"]
  },
  "preview_only": true
}
```

- Response (preview):
```json
{
  "markdown": "...",
  "tokens": 1832
}
```
- Response (persisted):
```json
{
  "source_id": "src_123",
  "chunks": 42,
  "provenance": {
    "source_type": "generated",
    "industry": "FinTech",
    "seed_prompt": "Produce a concise knowledge pack..."
  }
}
```

## Prompt Template (backend)
System: 
```
You write concise industry knowledge packs for B2B demo purposes.
Respond ONLY in markdown. Use bullet points, FAQs, and glossary style.
Cap length to 2000 tokens. Avoid hallucinating policies.
```
User: 
```
Industry: {industry}
Brand: {business_name}
Tagline: {tagline}
Hero: {hero_text}
Audience: {audience}
Tone: {tone}
Sections: {include_sections}
Constraints: {constraints}
```
Assistant: generates markdown.

## Ingestion
- Preview → Edit → Ingest
- Chunk size ≈800 tokens, 200 overlap
- Embedding with OpenAI `text-embedding-3-small`
- Store in Chroma with provenance fields

## Provenance
Every source row in `rag_sources`:
- source_type: "uploaded" | "generated"
- industry (if guided/quick)
- seed_prompt (if guided)
- created_at

## Safety
- Run Lakera pre-check on seed_prompt (guided) and post-check on generated markdown.
- Label Admin UI with “Generated Content (Industry: X)”
- Deduplicate similar chunks; strip active content (HTML, scripts).

---

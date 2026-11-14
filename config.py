"""Settings. Override any of these with environment variables (see .env.example)."""

import os

# Load settings from a .env file next to this one (works the same on Windows,
# macOS and Linux). Real environment variables still win.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:  # python-dotenv not installed: use environment variables only
    pass

# --- AWS -------------------------------------------------------------------
REGION = os.getenv("AWS_REGION", "ap-southeast-2")  # Sydney

# Claude Haiku 4.5 through the Australian inference profile: processing stays
# in Sydney and Melbourne. Customer documents only ever go to this model.
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "au.anthropic.claude-haiku-4-5-20251001-v1:0")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")

# Titan Text Embeddings V2 runs in Sydney.
EMBED_MODEL_ID = os.getenv("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")

# Optional: a Bedrock guardrail for the "ask the library" feature (step 6).
GUARDRAIL_ID = os.getenv("GUARDRAIL_ID", "")
GUARDRAIL_VERSION = os.getenv("GUARDRAIL_VERSION", "DRAFT")

# Optional: Amazon Textract for scanned PDFs and photos of paper checklists.
# Needs an S3 bucket in Sydney for multi-page scanned PDFs.
TEXTRACT_BUCKET = os.getenv("TEXTRACT_BUCKET", "")

# --- Which model --------------------------------------------------------------
#   bedrock = Claude on Bedrock (default; the only option allowed for customer documents)
#   nvidia  = an NVIDIA NIM model on build.nvidia.com (public guidance only: it is hosted outside Australia)
#   groq    = a Groq-hosted model (public guidance only: it is hosted outside Australia)
LLM_BACKEND = os.getenv("LLM_BACKEND", "bedrock")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
# Free tier output limit per call; raise if you upgrade to a paid Groq plan.
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "900"))

# --- Where the public guidance lives -----------------------------------------
#   kb    = your Bedrock Knowledge Base with S3 Vectors (step 3)
#   faiss = a local index built by ingest_guidance.py (no Knowledge Base needed)
RAG_BACKEND = os.getenv("RAG_BACKEND", "kb")
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "")
GUIDANCE_DIR = os.getenv("GUIDANCE_DIR", "guidance")
INDEX_DIR = os.getenv("INDEX_DIR", "index/guidance")

# --- Files --------------------------------------------------------------------
LIBRARY_CSV = os.getenv("LIBRARY_CSV", "data/requirements.csv")
CANDIDATES_CSV = os.getenv("CANDIDATES_CSV", "data/candidates.csv")
TOPICS_JSON = os.getenv("TOPICS_JSON", "data/topics.json")
EVIDENCE_JSON = os.getenv("EVIDENCE_JSON", "data/evidence_types.json")
REVIEWER = os.getenv("REVIEWER", "")  # your name, stamped on every verified row

# --- Retrieval and checking ----------------------------------------------------
TOP_K = int(os.getenv("TOP_K", "6"))              # guidance chunks per search
MAX_EXTRACTS_PER_TOPIC = 15                        # cap before extraction
EXTRACTS_PER_CALL = int(os.getenv("EXTRACTS_PER_CALL", "5"))  # smaller batches = more accurate quotes
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
SITE_TOP_K = int(os.getenv("SITE_TOP_K", "4"))    # site-document chunks per requirement
QUOTE_MATCH = float(os.getenv("QUOTE_MATCH", "0.90"))  # how close a quote must be to the source text

# Rough Claude Haiku 4.5 prices in USD per million tokens, for the cost line in
# each report. Check https://aws.amazon.com/bedrock/pricing/ and update.
PRICE_IN = float(os.getenv("PRICE_IN", "1.10"))
PRICE_OUT = float(os.getenv("PRICE_OUT", "5.50"))

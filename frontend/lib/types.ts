export type AccessType = "online" | "physical" | "both" | "unknown";
export type HoldingVerification = "verified_partner" | "catalogue_record" | "unverified" | "demo" | "online_item";
export type ReviewStatus = "draft" | "in_review" | "published" | "withdrawn";
export type LocationPrecision = "partner_verified" | "building" | "road" | "locality" | "demo" | "unknown";

export interface InstitutionCard {
  id: string;
  slug: string;
  name: string;
  kind: string;
  city?: string | null;
  region?: string | null;
  country?: string | null;
  website_url?: string | null;
  catalogue_url?: string | null;
  address?: string | null;
  access_requirements?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  collection_summary?: string | null;
  description?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  location_precision: LocationPrecision;
  location_source?: string | null;
  partner_status: "link_only" | "partner" | "demo";
  published_records?: number;
}

export interface LinkedRecord {
  id: string;
  institution_name: string | null;
  original_url: string;
  source_system: string;
}

export interface RecordCard {
  id: string;
  source_system: string;
  source_record_id: string;
  title: string;
  creators: string[];
  date_text?: string | null;
  date_start?: number | null;
  date_end?: number | null;
  resource_type: string;
  resource_type_label: string;
  language: string[];
  /** Display names for `language` in the requested locale (server-provided). */
  language_labels?: string[];
  subjects: string[];
  summary: string;
  description?: string | null;
  identifiers: Record<string, unknown>;
  institution: InstitutionCard | null;
  access_type: AccessType;
  access_note?: string | null;
  original_url: string;
  digital_url?: string | null;
  call_number?: string | null;
  shelf_label?: string | null;
  holding_verification: HoldingVerification;
  rights?: string | null;
  rights_status: string;
  has_full_text: boolean;
  thumbnail_url?: string | null;
  review_status: ReviewStatus;
  provenance: Record<string, unknown>;
  updated_at?: string | null;
  also_catalogued_at: LinkedRecord[];
  excerpts?: { page_number: number | null; page_url: string | null; text: string }[];
  raw_metadata?: Record<string, unknown>;
}

export interface Facet { value: string; count: number; label: string }

export interface Pin { institution: InstitutionCard; record_ids: string[]; count: number }

export interface SearchResponse {
  query: string;
  mode: "natural" | "advanced";
  total: number;
  page: number;
  page_size: number;
  results: RecordCard[];
  facets: Record<string, Facet[]>;
  pins: Pin[];
  unknown_location_count: number;
  online_only_count: number;
  online_resources: RecordCard[];
  alias_expansion: string[];
  capped: boolean;
  candidate_limit: number;
  date_from: number | null;
  date_to: number | null;
  keywords?: string;
  /** Where the person said they are ("I'm a student at Saint Mary's") — local results come first, the map opens there. */
  locality?: Locality | null;
}

export interface Locality {
  key: string;
  label: string;
  /** west, south, east, north */
  bbox: [number, number, number, number];
}

export interface Citation {
  n: number;
  evidence_id: string;
  record_id: string;
  chunk_id: string | null;
  quote: string | null;
  title: string;
  url: string;
  original_url: string;
  institution: string | null;
  institution_id: string | null;
  access_type: AccessType;
  page_number: number | null;
  kind: "record" | "chunk";
}

export interface GuideResponse {
  question: string;
  answer: string;
  citations: Citation[];
  abstain: boolean;
  abstain_reason: string | null;
  records: RecordCard[];
  highlight_record_ids: string[];
  map_focus_institution_ids: string[];
  provider: { name: string; model: string | null; configured: boolean };
  validation_error: string | null;
  evidence_count: number;
  follow_up?: boolean;
  cached?: boolean;
}

export interface SearchGaps {
  days: number;
  top_queries: { query: string; count: number; best_result_count: number }[];
  zero_result_queries: { query: string; count: number }[];
  guide_abstained: { query: string; count: number }[];
  latency: Record<string, { count: number; p50_ms: number; p95_ms: number }>;
}

export interface ConnectorStatus {
  name: string;
  label: string;
  state: "ok" | "unconfigured" | "blocked" | "error" | "untested";
  detail: string;
  docs_url: string | null;
  requires_key: boolean;
  key_env: string | null;
  checked_at: string | null;
  published_records: number;
  last_run: { status: string; query: string | null; fetched: number; upserted: number; started_at: string; error: string | null; request_url: string | null } | null;
}

export interface SourcesStatus {
  connectors: ConnectorStatus[];
  partner_published_records: number;
  full_text_chunks: number;
  ai: {
    guide: { name: string; model: string | null; configured: boolean };
    vision: { name: string; model: string | null; configured: boolean };
    embeddings: { provider: string; model: string };
    voice: { browser_speech: boolean; server_transcription: boolean; note: string };
  };
  map: { tiles: string; attribution: string; geocoder: string };
}

export interface Membership { institution_id: string; institution_name: string; institution_slug: string; role: "owner" | "editor" | "reviewer" }
export interface Me { id: string; email: string; display_name: string; memberships: Membership[] }

export interface ImportBatch {
  id: string;
  kind: string;
  filename: string | null;
  status: "preview" | "committed" | "failed";
  row_count: number;
  error_count: number;
  duplicate_count: number;
  committed_count: number;
  created_at: string;
  error: string | null;
  mapping: { headers: string[]; fields: Record<string, string | null> };
  canonical_fields: string[];
  preview?: PreviewRow[];
}

export interface PreviewRow {
  row_number: number;
  values: Record<string, unknown>;
  errors: string[];
  warnings: string[];
  duplicate_of: string | null;
  dedupe_key: string | null;
}

export interface Candidate {
  source: string;
  openlibrary_work_key: string;
  openlibrary_url: string | null;
  title: string | null;
  authors: string[];
  first_publish_year: number | null;
  publishers: string[];
  isbns: string[];
  edition_count: number | null;
  editions: string[];
  cover_id: number | null;
  score: number;
}

export interface ScanItem {
  id: string;
  position: number;
  spine_text: string | null;
  proposed_title: string | null;
  proposed_author: string | null;
  proposed_isbn: string | null;
  confidence: number | null;
  uncertainties: string[];
  candidates: Candidate[];
  selected_candidate: Candidate | null;
  call_number: string | null;
  shelf_label: string | null;
  confirmed_holding: boolean;
  status: "proposed" | "confirmed" | "rejected";
  record_id: string | null;
}

export interface ShelfScan {
  id: string;
  status: "queued" | "processing" | "proposed" | "reviewed" | "failed";
  model: string | null;
  error: string | null;
  created_at: string;
  image_url: string;
  items?: ScanItem[];
  job_id?: string;
}

export interface AuditEntry { id: string; at: string; actor: string | null; action: string; entity_type: string; entity_id: string | null; before: unknown; after: unknown }

export interface Dashboard {
  institution: InstitutionCard;
  role: string;
  records_by_status: Record<ReviewStatus, number>;
  import_batches: ImportBatch[];
  shelf_scans: ShelfScan[];
  jobs: { id: string; kind: string; status: string; error: string | null; created_at: string }[];
  recent_audit: AuditEntry[];
  sync: { mode: string; api_docs: string; last_import: string | null };
}

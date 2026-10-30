/**
 * TypeScript types mirroring `/api/v1/government` response and request schemas.
 *
 * OWNER: Ibrahim (API contract & typed client) / Gaurish (Government UI consumer)
 */

export type IssueType = 'cleaning' | 'maintenance'

export type IssueStatus =
  'open' | 'alert_sent' | 'acknowledged' | 'escalated' | 'resolved' | 'dismissed'

/**
 * Government triage classification for ordering follow-up work.
 *
 * IMPORTANT: This is NOT a cleanliness score, NOT a facility score, and NOT a
 * substitute for the intelligence module's official scoring engine owned by Shubham.
 */
export type TriageLevel = 'urgent' | 'high' | 'normal' | 'unranked'

export type VerificationStatus = 'verified' | 'unverified' | 'pending'

export type ConditionBand = 'recommended' | 'moderate' | 'attention' | 'unscored'

export type FeedbackSource = 'citizen_feedback' | 'evaluator_inspection'

export type FeedbackSentiment = 'positive' | 'neutral' | 'negative'

export type FeedbackCategory =
  | 'cleanliness_hygiene'
  | 'water_availability'
  | 'payment_experience'
  | 'broken_equipment'
  | 'locked_facility'
  | 'lighting'
  | 'accessibility'
  | 'safety'
  | 'overall_satisfaction'
  | 'other'

export type FeedbackChannel = 'app' | 'qr' | 'web' | 'iot'

export type CleanlinessVerdict = 'clean' | 'needs_cleaning' | 'insufficient_data'

export type NotificationChannel = 'email' | 'sms'

export type NotificationStatus = 'created' | 'sent' | 'failed' | 'acknowledged'

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface ResponsibleParty {
  name: string
  organization: string | null
  role_title: string | null
  email: string | null
  phone: string | null
  verified: boolean
}

export interface InspectionSummary {
  inspection_id: string
  facility_id: string
  evaluator_id: string | null
  inspected_at: string
  checklist_passed: boolean | null
  summary_note: string | null
  evidence_ids: string[]
}

export interface OfficialScore {
  value: number
  computed_at: string
  source: 'intelligence'
}

export interface DataQualityFlags {
  inspection_stale: boolean
  never_inspected: boolean
  missing_operator: boolean
  missing_location: boolean
  low_usage: boolean
  cleanliness_unknown: boolean
}

export interface CleanlinessWindow {
  facility_id: string
  window_start: string
  window_end: string
  yes_count: number
  no_count: number
  total: number
  negative_ratio: number
  verdict: CleanlinessVerdict
  action: 'none' | 'alert' | 'escalate' | 'insufficient_data'
  reasons: string[]
}

/**
 * Government triage classification result.
 *
 * NOT a cleanliness score or official facility score. Always label as
 * "Triage classification" in the UI, never "Score".
 */
export interface TriageResult {
  level: TriageLevel
  reasons: string[]
  responsibility_unverified: boolean
  classification_note: string
}

export interface FacilitySummary {
  id: string
  name: string
  ward: string
  address: string | null
  lat: number | null
  lng: number | null
  verification_status: VerificationStatus
  condition: ConditionBand
  official_score: OfficialScore | null
  latest_inspected_at: string | null
  data_quality: DataQualityFlags
  triage: TriageResult
}

export interface FacilityDetail {
  id: string
  name: string
  ward: string
  address: string | null
  lat: number | null
  lng: number | null
  verification_status: VerificationStatus
  condition: ConditionBand
  responsible_party: ResponsibleParty | null
  latest_inspection: InspectionSummary | null
  official_score: OfficialScore | null
  data_quality: DataQualityFlags
  latest_cleanliness_window: CleanlinessWindow | null
  triage: TriageResult
}

export interface CitizenFeedbackItem {
  id: string
  facility_id: string
  ward: string | null
  source: 'citizen_feedback'
  category: FeedbackCategory
  sentiment: FeedbackSentiment
  severity: number
  channel: FeedbackChannel
  comment: string | null
  reporter_hash: string | null
  linked_issue_id: string | null
  evidence_ids: string[]
  created_at: string
  age_hours: number
}

export interface FacilityFeedbackMeta {
  sentiment_breakdown: Record<string, number>
  cleanliness_windows: CleanlinessWindow[]
}

export interface FacilityFeedbackResponse extends PaginatedResponse<CitizenFeedbackItem> {
  meta: FacilityFeedbackMeta
}

export interface RepeatedComplaintCluster {
  facility_id: string
  facility_name: string | null
  ward: string | null
  category: FeedbackCategory
  count: number
  distinct_reporters: number
  first_seen: string
  last_seen: string
}

export interface IssueAuditEntry {
  from_status: IssueStatus | null
  to_status: IssueStatus
  actor_id: string
  note: string
  timestamp: string
}

export interface NotificationRecord {
  id: string
  issue_id: string
  channel: NotificationChannel
  recipient: string
  status: NotificationStatus
  created_at: string
  sent_at: string | null
  acknowledged_at: string | null
  provider_message: string | null
  payload: Record<string, unknown>
}

export interface MaintenanceIssue {
  id: string
  type: IssueType
  status: IssueStatus
  facility_id: string
  ward: string | null
  category: FeedbackCategory
  triage_level: TriageLevel
  summary: string
  responsibility_unverified: boolean
  consecutive_negative_windows: number
  verification_requested_at: string | null
  created_at: string
  updated_at: string
  history: IssueAuditEntry[]
  notifications: NotificationRecord[]
}

export interface OverviewStatistics {
  total_facilities: number
  recommended: number
  needing_attention: number
  unscored: number
  unverified: number
  pending_complaints: number
  active_issues: number
  escalated_issues: number
  resolved_issues: number
  recent_inspections: number
  positive_feedback_count: number
  negative_feedback_count: number
  cleanliness_alerts_last_24h: number
  facilities_low_usage: number
  facilities_cleanliness_unknown: number
  generated_at: string
  data_source: 'memory' | 'sql'
}

export interface EvaluationSummary {
  window_start: string
  window_end: string
  facilities_considered: number
  windows_saved: number
  skipped_existing: number
  clean: number
  needs_cleaning: number
  insufficient_data: number
  low_usage_flagged: number
  alerts_created: number
  alerts_emailed: number
  alerts_without_recipient: number
  escalations: number
  affected_facility_ids: string[]
  affected_issue_ids: string[]
  note: string
}

export interface MaintenanceDetectionSummary {
  evaluated_at: string
  facilities_considered: number
  issues_created: number
  existing_issues_noted: number
  created_issue_ids: string[]
}

export interface EvaluateResponse {
  cleanliness: EvaluationSummary
  maintenance: MaintenanceDetectionSummary
}

export interface FacilityListQuery {
  ward?: string
  verification_status?: VerificationStatus
  condition?: ConditionBand
  stale_only?: boolean
  low_usage_only?: boolean
  lat?: number
  lng?: number
  radius_m?: number
  page?: number
  page_size?: number
}

export interface FeedbackListQuery {
  facility_id?: string
  ward?: string
  category?: FeedbackCategory
  sentiment?: FeedbackSentiment
  severity?: number
  channel?: FeedbackChannel
  since?: string
  linked_to_issue?: boolean
  page?: number
  page_size?: number
}

export interface CleanlinessWindowQuery {
  facility_id?: string
  since?: string
  verdict?: CleanlinessVerdict
  page?: number
  page_size?: number
}

export interface IssueListQuery {
  status?: IssueStatus
  type?: IssueType
  triage_level?: TriageLevel
  ward?: string
  facility_id?: string
  page?: number
  page_size?: number
}

export interface IssueTransitionRequest {
  to_status: IssueStatus
  note?: string
}

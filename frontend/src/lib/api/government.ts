/**
 * Typed Axios client functions for `/api/v1/government/*`.
 *
 * OWNER: Ibrahim (API handoff) / Gaurish (UI consumer)
 */

import { apiClient } from './client'
import type {
  CitizenFeedbackItem,
  CleanlinessWindow,
  CleanlinessWindowQuery,
  EvaluateResponse,
  FacilityDetail,
  FacilityFeedbackResponse,
  FacilityListQuery,
  FacilitySummary,
  FeedbackListQuery,
  IssueListQuery,
  IssueTransitionRequest,
  MaintenanceIssue,
  NotificationChannel,
  NotificationRecord,
  OverviewStatistics,
  PaginatedResponse,
  RepeatedComplaintCluster,
} from './government.types'

export async function getGovernmentOverview(): Promise<OverviewStatistics> {
  const { data } = await apiClient.get<OverviewStatistics>('/government/overview')
  return data
}

export async function listGovernmentFacilities(
  params?: FacilityListQuery,
): Promise<PaginatedResponse<FacilitySummary>> {
  const { data } = await apiClient.get<PaginatedResponse<FacilitySummary>>(
    '/government/facilities',
    { params },
  )
  return data
}

export async function getGovernmentFacilityDetail(facilityId: string): Promise<FacilityDetail> {
  const { data } = await apiClient.get<FacilityDetail>(`/government/facilities/${facilityId}`)
  return data
}

export async function getGovernmentFacilityFeedback(
  facilityId: string,
  params?: { since?: string; page?: number; page_size?: number },
): Promise<FacilityFeedbackResponse> {
  const { data } = await apiClient.get<FacilityFeedbackResponse>(
    `/government/facilities/${facilityId}/feedback`,
    { params },
  )
  return data
}

export async function listGovernmentFeedback(
  params?: FeedbackListQuery,
): Promise<PaginatedResponse<CitizenFeedbackItem>> {
  const { data } = await apiClient.get<PaginatedResponse<CitizenFeedbackItem>>(
    '/government/feedback',
    { params },
  )
  return data
}

export async function listRepeatedComplaintClusters(params?: {
  facility_id?: string
  ward?: string
  page?: number
  page_size?: number
}): Promise<PaginatedResponse<RepeatedComplaintCluster>> {
  const { data } = await apiClient.get<PaginatedResponse<RepeatedComplaintCluster>>(
    '/government/feedback/repeated',
    { params },
  )
  return data
}

export async function triggerGovernmentEvaluation(): Promise<EvaluateResponse> {
  const { data } = await apiClient.post<EvaluateResponse>('/government/evaluate')
  return data
}

export async function listCleanlinessWindows(
  params?: CleanlinessWindowQuery,
): Promise<PaginatedResponse<CleanlinessWindow>> {
  const { data } = await apiClient.get<PaginatedResponse<CleanlinessWindow>>(
    '/government/cleanliness/windows',
    { params },
  )
  return data
}

export async function listGovernmentIssues(
  params?: IssueListQuery,
): Promise<PaginatedResponse<MaintenanceIssue>> {
  const { data } = await apiClient.get<PaginatedResponse<MaintenanceIssue>>('/government/issues', {
    params,
  })
  return data
}

export async function getGovernmentIssueDetail(issueId: string): Promise<MaintenanceIssue> {
  const { data } = await apiClient.get<MaintenanceIssue>(`/government/issues/${issueId}`)
  return data
}

export async function notifyIssueOperator(
  issueId: string,
  channel: NotificationChannel = 'email',
): Promise<NotificationRecord> {
  const { data } = await apiClient.post<NotificationRecord>(
    `/government/issues/${issueId}/notify`,
    { channel },
  )
  return data
}

export async function transitionGovernmentIssue(
  issueId: string,
  body: IssueTransitionRequest,
): Promise<MaintenanceIssue> {
  const { data } = await apiClient.post<MaintenanceIssue>(
    `/government/issues/${issueId}/transition`,
    body,
  )
  return data
}

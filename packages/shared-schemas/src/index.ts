export type AuditResult = "success" | "failure";

export interface AuditEvent {
  action: string;
  resourceType: string;
  resourceId?: string;
  result: AuditResult;
  occurredAt: string;
}


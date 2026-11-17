import { formatDistanceToNow, format } from 'date-fns';

export function parseDateUtc(dateInput: string | Date | null | undefined): Date | null {
  if (!dateInput) return null;
  if (dateInput instanceof Date) return dateInput;
  if (typeof dateInput === 'string') {
    // If string has no timezone indicator (no 'Z' and no offset like '+05:30' or '-04:00'), treat as UTC
    const hasTz = dateInput.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(dateInput);
    const normalized = hasTz ? dateInput : `${dateInput}Z`;
    const d = new Date(normalized);
    if (!isNaN(d.getTime())) return d;
  }
  const fallback = new Date(dateInput);
  return isNaN(fallback.getTime()) ? null : fallback;
}

export function safeFormatDistanceToNow(dateInput: string | Date | null | undefined): string {
  const d = parseDateUtc(dateInput);
  if (!d) return 'recently';
  return formatDistanceToNow(d, { addSuffix: true });
}

export function safeFormatDate(dateInput: string | Date | null | undefined, fmtStr: string = 'PPpp'): string {
  const d = parseDateUtc(dateInput);
  if (!d) return '';
  return format(d, fmtStr);
}

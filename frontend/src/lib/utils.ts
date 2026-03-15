import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(date: string | Date): string {
  return new Date(date).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatCurrency(amount: number | string, currency = 'USD'): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(num)
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num)
}

export function formatPercentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str
  return str.slice(0, maxLength - 3) + '...'
}

export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    // General statuses
    completed: 'bg-green-100 text-green-800',
    success: 'bg-green-100 text-green-800',
    active: 'bg-green-100 text-green-800',
    matched: 'bg-green-100 text-green-800',
    resolved: 'bg-green-100 text-green-800',

    pending: 'bg-yellow-100 text-yellow-800',
    processing: 'bg-blue-100 text-blue-800',
    running: 'bg-blue-100 text-blue-800',
    in_review: 'bg-blue-100 text-blue-800',

    failed: 'bg-red-100 text-red-800',
    error: 'bg-red-100 text-red-800',
    unmatched: 'bg-red-100 text-red-800',

    cancelled: 'bg-gray-100 text-gray-800',
    dismissed: 'bg-gray-100 text-gray-800',

    escalated: 'bg-purple-100 text-purple-800',
    open: 'bg-orange-100 text-orange-800',
  }

  return colors[status.toLowerCase()] || 'bg-gray-100 text-gray-800'
}

export function getSeverityColor(severity: string): string {
  const colors: Record<string, string> = {
    low: 'bg-blue-100 text-blue-800',
    medium: 'bg-yellow-100 text-yellow-800',
    high: 'bg-orange-100 text-orange-800',
    critical: 'bg-red-100 text-red-800',
  }

  return colors[severity.toLowerCase()] || 'bg-gray-100 text-gray-800'
}

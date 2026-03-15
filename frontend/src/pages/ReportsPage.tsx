import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reportsApi, aiApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatDateTime, getStatusColor } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'
import {
  FileText,
  Download,
  Plus,
  Clock,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  FileSpreadsheet,
  FileJson,
  Trash2,
  Sparkles,
} from 'lucide-react'

const REPORT_TYPES = [
  { value: 'reconciliation_summary', label: 'Reconciliation Summary', description: 'Match rates and run statistics' },
  { value: 'unmatched_items', label: 'Unmatched Items', description: 'Records without matches' },
  { value: 'exception_backlog', label: 'Exception Backlog', description: 'Open exceptions by severity' },
  { value: 'anomaly_report', label: 'Anomaly Report', description: 'Detected anomalies by type' },
  { value: 'ingestion_health', label: 'Ingestion Health', description: 'Job status and validation rates' },
  { value: 'operational_summary', label: 'Operational Summary', description: 'Cross-system metrics' },
  { value: 'match_analysis', label: 'Match Analysis', description: 'Match candidates by score distribution' },
]

const FILE_FORMATS = [
  { value: 'csv', label: 'CSV', icon: FileText },
  { value: 'excel', label: 'Excel', icon: FileSpreadsheet },
  { value: 'json', label: 'JSON', icon: FileJson },
]

export function ReportsPage() {
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newReport, setNewReport] = useState({
    report_type: 'reconciliation_summary',
    title: '',
    file_format: 'csv',
    filters: {},
    parameters: {},
  })
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: reportsData, isLoading, refetch } = useQuery({
    queryKey: ['reports'],
    queryFn: () => reportsApi.list({ limit: 50 }),
    refetchInterval: 5000, // Poll for status updates
  })

  const createMutation = useMutation({
    mutationFn: (data: typeof newReport) => reportsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      setShowCreateForm(false)
      setNewReport({
        report_type: 'reconciliation_summary',
        title: '',
        file_format: 'csv',
        filters: {},
        parameters: {},
      })
      toast({ title: 'Report generation started', description: 'You will be notified when it completes.' })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to create report',
        description: error.response?.data?.detail || 'An error occurred',
        variant: 'destructive',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => reportsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      toast({ title: 'Report deleted' })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to delete report',
        description: error.response?.data?.detail || 'An error occurred',
        variant: 'destructive',
      })
    },
  })

  const aiExplanationMutation = useMutation({
    mutationFn: (reportId: string) => aiApi.requestReportExplanation(reportId),
    onSuccess: async (data) => {
      // API returns immediately with status: "pending"
      // We need to poll until the summary is ready
      const explanationId = data.id
      toast({ title: 'Generating AI Summary...', description: 'This may take a few seconds.' })

      const pollForExplanation = async (attempts = 0) => {
        if (attempts >= 30) {
          toast({ title: 'AI Summary', description: 'Generation timed out. Please try again.', variant: 'destructive' })
          return
        }

        try {
          const result = await aiApi.get(explanationId)
          if (result.status === 'completed' && result.output_text) {
            toast({
              title: 'AI Summary Ready',
              description: result.output_text.substring(0, 200) + (result.output_text.length > 200 ? '...' : ''),
            })
            queryClient.invalidateQueries({ queryKey: ['reports'] })
          } else if (result.status === 'failed') {
            toast({ title: 'AI Summary Failed', description: result.error_message || 'Unknown error', variant: 'destructive' })
          } else {
            // Still pending/processing, poll again
            setTimeout(() => pollForExplanation(attempts + 1), 1000)
          }
        } catch {
          toast({ title: 'Failed to fetch summary', variant: 'destructive' })
        }
      }

      pollForExplanation()
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to get AI summary',
        description: error.response?.data?.detail || 'AI service unavailable',
        variant: 'destructive',
      })
    },
  })

  const handleDelete = (reportId: string, title: string) => {
    if (confirm(`Delete report "${title}"? This cannot be undone.`)) {
      deleteMutation.mutate(reportId)
    }
  }

  const handleCreateReport = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newReport.title.trim()) {
      toast({ title: 'Title required', variant: 'destructive' })
      return
    }
    createMutation.mutate(newReport)
  }

  const handleDownload = async (reportId: string, title: string, format: string) => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/reports/${reportId}/download`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
      })
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Download failed' }))
        throw new Error(error.detail || 'Download failed')
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const ext = format === 'excel' ? 'xlsx' : format
      a.download = `${title}.${ext}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      toast({ title: 'Download started' })
    } catch (error: any) {
      toast({ title: 'Download failed', description: error.message, variant: 'destructive' })
    }
  }

  const reports = reportsData?.items || []

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-600" />
      case 'generating':
      case 'pending':
        return <Clock className="h-4 w-4 text-blue-600 animate-pulse" />
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-600" />
      default:
        return null
    }
  }

  const getFormatIcon = (format: string) => {
    const formatConfig = FILE_FORMATS.find(f => f.value === format)
    if (formatConfig) {
      const Icon = formatConfig.icon
      return <Icon className="h-4 w-4" />
    }
    return <FileText className="h-4 w-4" />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Reports</h1>
          <p className="text-muted-foreground">
            Generate and download operational reports
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button onClick={() => setShowCreateForm(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Generate Report
          </Button>
        </div>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <Card className="border-primary/50">
          <CardHeader>
            <CardTitle>Generate New Report</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateReport} className="space-y-6">
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="report_type">Report Type</Label>
                  <select
                    id="report_type"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    value={newReport.report_type}
                    onChange={(e) => setNewReport({ ...newReport, report_type: e.target.value })}
                  >
                    {REPORT_TYPES.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    {REPORT_TYPES.find(t => t.value === newReport.report_type)?.description}
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="title">Report Title</Label>
                  <Input
                    id="title"
                    value={newReport.title}
                    onChange={(e) => setNewReport({ ...newReport, title: e.target.value })}
                    placeholder="e.g., March 2024 Reconciliation Summary"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Output Format</Label>
                <div className="flex gap-2">
                  {FILE_FORMATS.map((format) => {
                    const Icon = format.icon
                    return (
                      <Button
                        key={format.value}
                        type="button"
                        variant={newReport.file_format === format.value ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setNewReport({ ...newReport, file_format: format.value })}
                        className="flex-1"
                      >
                        <Icon className="mr-2 h-4 w-4" />
                        {format.label}
                      </Button>
                    )
                  })}
                </div>
              </div>

              <div className="flex gap-2">
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      Starting...
                    </>
                  ) : (
                    <>
                      <FileText className="mr-2 h-4 w-4" />
                      Generate Report
                    </>
                  )}
                </Button>
                <Button type="button" variant="outline" onClick={() => setShowCreateForm(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Reports Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : reports.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {reports.map((report: any) => (
            <Card key={report.id} className="hover:shadow-md transition-shadow">
              <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                    {getFormatIcon(report.file_format)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-lg truncate">{report.title}</CardTitle>
                    <p className="text-sm text-muted-foreground capitalize">
                      {report.report_type.replace(/_/g, ' ')}
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between mb-4">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusColor(report.status)}`}>
                    {getStatusIcon(report.status)}
                    <span className="capitalize">{report.status}</span>
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatDateTime(report.created_at)}
                  </span>
                </div>

                {report.error_message && (
                  <p className="text-xs text-red-600 mb-3 truncate" title={report.error_message}>
                    {report.error_message}
                  </p>
                )}

                {report.status === 'completed' && (
                  <div className="space-y-2">
                    <Button
                      className="w-full"
                      variant="outline"
                      onClick={() => handleDownload(report.id, report.title, report.file_format)}
                    >
                      <Download className="mr-2 h-4 w-4" />
                      Download {report.file_format?.toUpperCase() || 'CSV'}
                    </Button>
                    <div className="flex gap-2">
                      <Button
                        className="flex-1"
                        variant="outline"
                        size="sm"
                        onClick={() => aiExplanationMutation.mutate(report.id)}
                        disabled={aiExplanationMutation.isPending}
                      >
                        <Sparkles className="mr-2 h-4 w-4" />
                        AI Summary
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDelete(report.id, report.title)}
                        disabled={deleteMutation.isPending}
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}

                {(report.status === 'pending' || report.status === 'generating') && (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Generating report...
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(report.id, report.title)}
                      disabled={deleteMutation.isPending}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                )}

                {report.status === 'failed' && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDelete(report.id, report.title)}
                    disabled={deleteMutation.isPending}
                    className="w-full text-destructive hover:text-destructive"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete Failed Report
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">No reports yet</h3>
            <p className="text-muted-foreground mb-4 text-center">
              Generate your first report to get insights into your reconciliation operations
            </p>
            <Button onClick={() => setShowCreateForm(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Generate Report
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Report Types Reference */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Available Report Types</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {REPORT_TYPES.map((type) => (
              <div key={type.value} className="flex items-start gap-3 p-3 rounded-lg border bg-muted/30">
                <FileText className="h-5 w-5 text-primary mt-0.5" />
                <div>
                  <p className="font-medium text-sm">{type.label}</p>
                  <p className="text-xs text-muted-foreground">{type.description}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

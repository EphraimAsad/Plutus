import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { exceptionsApi, reconciliationApi, aiApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatDateTime, getStatusColor, getSeverityColor, formatCurrency } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  ArrowUp,
  Eye,
  X,
  MessageSquare,
  UserPlus,
  ChevronRight,
  ChevronDown,
  History,
  Sparkles,
} from 'lucide-react'

interface Exception {
  id: string
  title: string
  description: string | null
  exception_type: string
  severity: string
  status: string
  created_at: string
  updated_at: string
  assigned_to: string | null
  resolved_at: string | null
  resolution_note: string | null
  related_record_ids: string[]
  related_match_candidate_ids: string[]
}

export function ExceptionsPage() {
  const [selectedStatus, setSelectedStatus] = useState<string>('')
  const [selectedSeverity, setSelectedSeverity] = useState<string>('')
  const [selectedException, setSelectedException] = useState<Exception | null>(null)
  const [resolutionNote, setResolutionNote] = useState('')
  const [showDetailPanel, setShowDetailPanel] = useState(false)
  const [showPreviousExceptions, setShowPreviousExceptions] = useState(false)
  const [aiExplanation, setAiExplanation] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: exceptionsData, isLoading } = useQuery({
    queryKey: ['exceptions', selectedStatus, selectedSeverity],
    queryFn: () =>
      exceptionsApi.list({
        status: selectedStatus || undefined,
        severity: selectedSeverity || undefined,
        limit: 100,
      }),
  })

  // Fetch related records when an exception is selected
  const { data: relatedRecords } = useQuery({
    queryKey: ['exception-records', selectedException?.id],
    queryFn: async () => {
      if (!selectedException?.related_match_candidate_ids?.[0]) return null
      return reconciliationApi.getCandidateRecords(selectedException.related_match_candidate_ids[0])
    },
    enabled: !!selectedException?.related_match_candidate_ids?.[0],
  })

  // Fetch notes for selected exception
  const { data: notes } = useQuery({
    queryKey: ['exception-notes', selectedException?.id],
    queryFn: () => exceptionsApi.getNotes(selectedException!.id),
    enabled: !!selectedException,
  })

  const resolveMutation = useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) => exceptionsApi.resolve(id, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exceptions'] })
      setShowDetailPanel(false)
      setSelectedException(null)
      setResolutionNote('')
      toast({ title: 'Exception resolved' })
    },
  })

  const dismissMutation = useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) => exceptionsApi.dismiss(id, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exceptions'] })
      setShowDetailPanel(false)
      setSelectedException(null)
      setResolutionNote('')
      toast({ title: 'Exception dismissed' })
    },
  })

  const escalateMutation = useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) => exceptionsApi.escalate(id, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exceptions'] })
      toast({ title: 'Exception escalated' })
    },
  })

  const addNoteMutation = useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) =>
      exceptionsApi.addNote(id, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exception-notes', selectedException?.id] })
      toast({ title: 'Note added' })
    },
  })

  const aiExplanationMutation = useMutation({
    mutationFn: (exceptionId: string) => aiApi.requestExceptionExplanation(exceptionId),
    onSuccess: async (data) => {
      // API returns immediately with status: "pending"
      // We need to poll until the explanation is ready
      const explanationId = data.id
      setAiExplanation('Generating AI explanation...')

      const pollForExplanation = async (attempts = 0) => {
        if (attempts >= 30) {
          setAiExplanation('Explanation generation timed out. Please try again.')
          return
        }

        try {
          const result = await aiApi.get(explanationId)
          if (result.status === 'completed' && result.output_text) {
            setAiExplanation(result.output_text)
            toast({ title: 'AI Explanation ready' })
          } else if (result.status === 'failed') {
            setAiExplanation('Failed to generate explanation: ' + (result.error_message || 'Unknown error'))
          } else {
            // Still pending/processing, poll again
            setTimeout(() => pollForExplanation(attempts + 1), 1000)
          }
        } catch {
          setAiExplanation('Failed to fetch explanation')
        }
      }

      pollForExplanation()
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to get AI explanation',
        description: error.response?.data?.detail || 'AI service unavailable',
        variant: 'destructive',
      })
    },
  })

  const exceptions = exceptionsData?.items || []
  const total = exceptionsData?.total || 0

  // Split into active and previous exceptions
  const activeExceptions = exceptions.filter((e: Exception) =>
    !['resolved', 'dismissed'].includes(e.status)
  )
  const previousExceptions = exceptions.filter((e: Exception) =>
    ['resolved', 'dismissed'].includes(e.status)
  )

  // Summary counts
  const openCount = exceptions.filter((e: Exception) => e.status === 'open' || e.status === 'in_review').length
  const criticalCount = exceptions.filter((e: Exception) => e.severity === 'critical').length
  const highCount = exceptions.filter((e: Exception) => e.severity === 'high').length

  const handleViewException = (exception: Exception) => {
    setSelectedException(exception)
    setShowDetailPanel(true)
    setResolutionNote('')
    setAiExplanation(null)
  }

  const handleClosePanel = () => {
    setShowDetailPanel(false)
    setSelectedException(null)
    setResolutionNote('')
    setAiExplanation(null)
  }

  const handleResolve = () => {
    if (selectedException) {
      resolveMutation.mutate({ id: selectedException.id, note: resolutionNote || undefined })
    }
  }

  const handleDismiss = () => {
    if (selectedException) {
      dismissMutation.mutate({ id: selectedException.id, note: resolutionNote || undefined })
    }
  }

  const handleEscalate = () => {
    if (selectedException) {
      escalateMutation.mutate({ id: selectedException.id, note: resolutionNote || undefined })
    }
  }

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <AlertTriangle className="h-4 w-4 text-red-600" />
      case 'high':
        return <ArrowUp className="h-4 w-4 text-orange-500" />
      case 'medium':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />
      default:
        return <AlertTriangle className="h-4 w-4 text-blue-500" />
    }
  }

  return (
    <div className="flex h-full">
      {/* Main Content */}
      <div className={`flex-1 space-y-6 transition-all ${showDetailPanel ? 'pr-96' : ''}`}>
        <div>
          <h1 className="text-3xl font-bold">Exception Queue</h1>
          <p className="text-muted-foreground">
            Review and resolve reconciliation exceptions
          </p>
        </div>

        {/* Summary Cards */}
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <AlertTriangle className="h-8 w-8 text-orange-500" />
                <div>
                  <p className="text-2xl font-bold">{total}</p>
                  <p className="text-sm text-muted-foreground">Total Exceptions</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <Eye className="h-8 w-8 text-blue-500" />
                <div>
                  <p className="text-2xl font-bold">{openCount}</p>
                  <p className="text-sm text-muted-foreground">Open / In Review</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <AlertTriangle className="h-8 w-8 text-red-500" />
                <div>
                  <p className="text-2xl font-bold">{criticalCount}</p>
                  <p className="text-sm text-muted-foreground">Critical</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <ArrowUp className="h-8 w-8 text-orange-500" />
                <div>
                  <p className="text-2xl font-bold">{highCount}</p>
                  <p className="text-sm text-muted-foreground">High Priority</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex gap-4 flex-wrap">
              <select
                className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
              >
                <option value="">All Statuses</option>
                <option value="open">Open</option>
                <option value="in_review">In Review</option>
                <option value="resolved">Resolved</option>
                <option value="dismissed">Dismissed</option>
                <option value="escalated">Escalated</option>
              </select>
              <select
                className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
              >
                <option value="">All Severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </CardContent>
        </Card>

        {/* Active Exceptions Table */}
        <Card>
          <CardHeader>
            <CardTitle>Active Exceptions ({activeExceptions.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-8">Loading...</div>
            ) : activeExceptions.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-3 px-4 font-medium">Severity</th>
                      <th className="text-left py-3 px-4 font-medium">Title</th>
                      <th className="text-left py-3 px-4 font-medium">Type</th>
                      <th className="text-left py-3 px-4 font-medium">Status</th>
                      <th className="text-left py-3 px-4 font-medium">Created</th>
                      <th className="text-left py-3 px-4 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeExceptions.map((exception: Exception) => (
                      <tr
                        key={exception.id}
                        className={`border-b hover:bg-muted/50 cursor-pointer ${
                          selectedException?.id === exception.id ? 'bg-muted/50' : ''
                        }`}
                        onClick={() => handleViewException(exception)}
                      >
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            {getSeverityIcon(exception.severity)}
                            <span className={`rounded-full px-2 py-1 text-xs ${getSeverityColor(exception.severity)}`}>
                              {exception.severity}
                            </span>
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <div className="max-w-md">
                            <p className="font-medium truncate">{exception.title}</p>
                            {exception.description && (
                              <p className="text-sm text-muted-foreground truncate">
                                {exception.description}
                              </p>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="text-sm capitalize">
                            {exception.exception_type.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`rounded-full px-2 py-1 text-xs ${getStatusColor(exception.status)}`}>
                            {exception.status.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-muted-foreground text-sm">
                          {formatDateTime(exception.created_at)}
                        </td>
                        <td className="py-3 px-4">
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12">
                <CheckCircle className="h-12 w-12 text-green-500 mb-4" />
                <h3 className="text-lg font-medium">No active exceptions</h3>
                <p className="text-muted-foreground">
                  All clear! No exceptions require attention.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Previous Exceptions (Collapsed) */}
        {previousExceptions.length > 0 && (
          <Card>
            <div
              className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted/50"
              onClick={() => setShowPreviousExceptions(!showPreviousExceptions)}
            >
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <History className="h-5 w-5" />
                Previous Exceptions ({previousExceptions.length})
              </h3>
              <ChevronDown className={`h-5 w-5 transition-transform ${showPreviousExceptions ? 'rotate-180' : ''}`} />
            </div>
            {showPreviousExceptions && (
              <CardContent className="pt-0">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-3 px-4 font-medium">Severity</th>
                        <th className="text-left py-3 px-4 font-medium">Title</th>
                        <th className="text-left py-3 px-4 font-medium">Type</th>
                        <th className="text-left py-3 px-4 font-medium">Status</th>
                        <th className="text-left py-3 px-4 font-medium">Resolved</th>
                        <th className="text-left py-3 px-4 font-medium"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {previousExceptions.map((exception: Exception) => (
                        <tr
                          key={exception.id}
                          className={`border-b hover:bg-muted/50 cursor-pointer ${
                            selectedException?.id === exception.id ? 'bg-muted/50' : ''
                          }`}
                          onClick={() => handleViewException(exception)}
                        >
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2">
                              {getSeverityIcon(exception.severity)}
                              <span className={`rounded-full px-2 py-1 text-xs ${getSeverityColor(exception.severity)}`}>
                                {exception.severity}
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <div className="max-w-md">
                              <p className="font-medium truncate">{exception.title}</p>
                              {exception.description && (
                                <p className="text-sm text-muted-foreground truncate">
                                  {exception.description}
                                </p>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <span className="text-sm capitalize">
                              {exception.exception_type.replace(/_/g, ' ')}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className={`rounded-full px-2 py-1 text-xs ${getStatusColor(exception.status)}`}>
                              {exception.status.replace(/_/g, ' ')}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-muted-foreground text-sm">
                            {exception.resolved_at ? formatDateTime(exception.resolved_at) : '-'}
                          </td>
                          <td className="py-3 px-4">
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            )}
          </Card>
        )}
      </div>

      {/* Detail Panel */}
      {showDetailPanel && selectedException && (
        <div className="fixed right-0 top-0 h-full w-96 bg-background border-l shadow-lg overflow-y-auto z-50">
          <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                {getSeverityIcon(selectedException.severity)}
                <span className={`rounded-full px-2 py-1 text-xs ${getSeverityColor(selectedException.severity)}`}>
                  {selectedException.severity}
                </span>
                <span className={`rounded-full px-2 py-1 text-xs ${getStatusColor(selectedException.status)}`}>
                  {selectedException.status}
                </span>
              </div>
              <Button variant="ghost" size="sm" onClick={handleClosePanel}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Title & Description */}
            <div>
              <h2 className="text-lg font-semibold">{selectedException.title}</h2>
              {selectedException.description && (
                <p className="text-sm text-muted-foreground mt-1">{selectedException.description}</p>
              )}
              <p className="text-xs text-muted-foreground mt-2">
                Type: {selectedException.exception_type.replace(/_/g, ' ')}
              </p>
              <p className="text-xs text-muted-foreground">
                Created: {formatDateTime(selectedException.created_at)}
              </p>
            </div>

            {/* AI Explanation */}
            <div className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => aiExplanationMutation.mutate(selectedException.id)}
                disabled={aiExplanationMutation.isPending}
              >
                <Sparkles className="mr-2 h-4 w-4" />
                {aiExplanationMutation.isPending ? 'Getting AI Explanation...' : 'Get AI Explanation'}
              </Button>
              {aiExplanation && (
                <div className="p-3 bg-primary/5 border border-primary/20 rounded-lg">
                  <p className="text-xs font-medium text-primary mb-1 flex items-center gap-1">
                    <Sparkles className="h-3 w-3" />
                    AI Analysis
                  </p>
                  <p className="text-sm">{aiExplanation}</p>
                </div>
              )}
            </div>

            {/* Related Records Comparison */}
            {relatedRecords?.left_record && relatedRecords?.right_record && (
              <div className="space-y-4">
                <h3 className="font-medium text-sm">Record Comparison</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="p-3 bg-muted rounded-lg">
                    <p className="font-medium text-xs mb-2">Left Record</p>
                    <div className="space-y-1">
                      <p><span className="text-muted-foreground">ID:</span> {relatedRecords.left_record.external_record_id || '-'}</p>
                      <p><span className="text-muted-foreground">Date:</span> {relatedRecords.left_record.record_date || '-'}</p>
                      <p><span className="text-muted-foreground">Amount:</span> {formatCurrency(relatedRecords.left_record.amount, relatedRecords.left_record.currency)}</p>
                      <p className="truncate"><span className="text-muted-foreground">Ref:</span> {relatedRecords.left_record.reference_code || '-'}</p>
                    </div>
                  </div>
                  <div className="p-3 bg-muted rounded-lg">
                    <p className="font-medium text-xs mb-2">Right Record</p>
                    <div className="space-y-1">
                      <p><span className="text-muted-foreground">ID:</span> {relatedRecords.right_record.external_record_id || '-'}</p>
                      <p><span className="text-muted-foreground">Date:</span> {relatedRecords.right_record.record_date || '-'}</p>
                      <p><span className="text-muted-foreground">Amount:</span> {formatCurrency(relatedRecords.right_record.amount, relatedRecords.right_record.currency)}</p>
                      <p className="truncate"><span className="text-muted-foreground">Ref:</span> {relatedRecords.right_record.reference_code || '-'}</p>
                    </div>
                  </div>
                </div>
                {relatedRecords.score && (
                  <p className="text-xs text-muted-foreground">
                    Match Score: {(relatedRecords.score * 100).toFixed(1)}%
                  </p>
                )}
              </div>
            )}

            {/* Notes */}
            {notes && notes.length > 0 && (
              <div className="space-y-2">
                <h3 className="font-medium text-sm flex items-center gap-2">
                  <MessageSquare className="h-4 w-4" />
                  Notes ({notes.length})
                </h3>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {notes.map((note: any) => (
                    <div key={note.id} className="p-2 bg-muted rounded text-sm">
                      <p>{note.content}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {formatDateTime(note.created_at)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Resolution Form */}
            {(selectedException.status === 'open' || selectedException.status === 'in_review') && (
              <div className="space-y-4 border-t pt-4">
                <div className="space-y-2">
                  <Label htmlFor="resolution-note">Resolution Note</Label>
                  <textarea
                    id="resolution-note"
                    className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[80px]"
                    placeholder="Add notes about the resolution..."
                    value={resolutionNote}
                    onChange={(e) => setResolutionNote(e.target.value)}
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <Button
                    onClick={handleResolve}
                    disabled={resolveMutation.isPending}
                    className="w-full"
                  >
                    <CheckCircle className="mr-2 h-4 w-4" />
                    Resolve
                  </Button>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      onClick={handleDismiss}
                      disabled={dismissMutation.isPending}
                      className="flex-1"
                    >
                      <XCircle className="mr-2 h-4 w-4" />
                      Dismiss
                    </Button>
                    <Button
                      variant="outline"
                      onClick={handleEscalate}
                      disabled={escalateMutation.isPending}
                      className="flex-1"
                    >
                      <ArrowUp className="mr-2 h-4 w-4" />
                      Escalate
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* Already Resolved */}
            {selectedException.status === 'resolved' && selectedException.resolution_note && (
              <div className="border-t pt-4">
                <h3 className="font-medium text-sm mb-2">Resolution</h3>
                <p className="text-sm text-muted-foreground">{selectedException.resolution_note}</p>
                {selectedException.resolved_at && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Resolved: {formatDateTime(selectedException.resolved_at)}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

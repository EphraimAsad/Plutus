import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { reconciliationApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTime, formatNumber, formatCurrency, formatPercentage, getStatusColor } from '@/lib/utils'
import { ArrowLeft, CheckCircle, XCircle, Clock, GitCompare, AlertTriangle, HelpCircle } from 'lucide-react'

export function ReconciliationDetailsPage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()

  const { data: run, isLoading: runLoading } = useQuery({
    queryKey: ['reconciliation-run', runId],
    queryFn: () => reconciliationApi.getRun(runId!),
    enabled: !!runId,
  })

  const { data: confirmedMatches } = useQuery({
    queryKey: ['reconciliation-confirmed-matches', runId],
    queryFn: () => reconciliationApi.getConfirmedMatches(runId!, { limit: 50 }),
    enabled: !!runId,
  })

  const { data: candidates } = useQuery({
    queryKey: ['reconciliation-candidates', runId],
    queryFn: () => reconciliationApi.getMatches(runId!, { limit: 50 }),
    enabled: !!runId,
  })

  const { data: unmatched } = useQuery({
    queryKey: ['reconciliation-unmatched', runId],
    queryFn: () => reconciliationApi.getUnmatched(runId!, { limit: 50 }),
    enabled: !!runId,
  })

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />
      default:
        return <Clock className="h-5 w-5 text-yellow-500" />
    }
  }

  const calculateMatchRate = () => {
    if (!run) return 0
    const total = (run.total_left_records || 0) + (run.total_right_records || 0)
    const matched = (run.total_matched || 0) * 2
    return total > 0 ? matched / total : 0
  }

  if (runLoading) {
    return <div className="flex items-center justify-center p-8">Loading...</div>
  }

  if (!run) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate('/reconciliation')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Reconciliation
        </Button>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">Run not found</h3>
            <p className="text-muted-foreground">The requested reconciliation run could not be found.</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => navigate('/reconciliation')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <GitCompare className="h-6 w-6 text-primary" />
            <h1 className="text-3xl font-bold">{run.name}</h1>
            <div className="flex items-center gap-2">
              {getStatusIcon(run.status)}
              <span className={`rounded-full px-2 py-1 text-xs ${getStatusColor(run.status)}`}>
                {run.status}
              </span>
            </div>
          </div>
          <p className="text-muted-foreground mt-1">
            Created {formatDateTime(run.created_at)}
            {run.completed_at && ` | Completed ${formatDateTime(run.completed_at)}`}
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Left Records</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(run.total_left_records || 0)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Right Records</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(run.total_right_records || 0)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Auto-Matched</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{formatNumber(confirmedMatches?.length || 0)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Needs Review</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{formatNumber(candidates?.length || 0)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Unmatched</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{formatNumber(unmatched?.length || 0)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Parameters */}
      {run.parameters_json && (
        <Card>
          <CardHeader>
            <CardTitle>Run Parameters</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <span className="text-sm text-muted-foreground">Date Tolerance:</span>
                <span className="ml-2 font-medium">{run.parameters_json.date_tolerance_days || 0} days</span>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">Amount Tolerance:</span>
                <span className="ml-2 font-medium">{run.parameters_json.amount_tolerance_percent || 0}%</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Confirmed Matches */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-green-500" />
            Confirmed Matches ({confirmedMatches?.length || 0})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {confirmedMatches?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-4 font-medium">Left Record</th>
                    <th className="text-left py-3 px-4 font-medium">Right Record</th>
                    <th className="text-right py-3 px-4 font-medium">Left Amount</th>
                    <th className="text-right py-3 px-4 font-medium">Right Amount</th>
                    <th className="text-left py-3 px-4 font-medium">Left Date</th>
                    <th className="text-left py-3 px-4 font-medium">Right Date</th>
                    <th className="text-right py-3 px-4 font-medium">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {confirmedMatches.map((match: any, index: number) => (
                    <tr key={match.id || index} className="border-b hover:bg-muted/50">
                      <td className="py-3 px-4 font-mono text-sm">
                        {match.left_record?.external_record_id || '-'}
                      </td>
                      <td className="py-3 px-4 font-mono text-sm">
                        {match.right_record?.external_record_id || '-'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        {match.left_record?.amount ? formatCurrency(match.left_record.amount) : '-'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        {match.right_record?.amount ? formatCurrency(match.right_record.amount) : '-'}
                      </td>
                      <td className="py-3 px-4">
                        {match.left_record?.record_date || '-'}
                      </td>
                      <td className="py-3 px-4">
                        {match.right_record?.record_date || '-'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className="rounded-full bg-green-100 text-green-800 px-2 py-1 text-xs">
                          {match.confidence_score ? `${(match.confidence_score * 100).toFixed(0)}%` : '100%'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8">
              <CheckCircle className="h-8 w-8 text-muted-foreground mb-2" />
              <p className="text-muted-foreground">No confirmed matches</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Candidates Needing Review */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HelpCircle className="h-5 w-5 text-yellow-500" />
            Candidates Needing Review ({candidates?.length || 0})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {candidates?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-4 font-medium">Match Type</th>
                    <th className="text-left py-3 px-4 font-medium">Left Record</th>
                    <th className="text-left py-3 px-4 font-medium">Right Record</th>
                    <th className="text-right py-3 px-4 font-medium">Score</th>
                    <th className="text-left py-3 px-4 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((candidate: any, index: number) => (
                    <tr key={candidate.id || index} className="border-b hover:bg-muted/50">
                      <td className="py-3 px-4">
                        <span className="rounded-full bg-yellow-100 text-yellow-800 px-2 py-1 text-xs">
                          {candidate.match_type}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-sm">
                        {candidate.left_record_id?.substring(0, 8) || '-'}
                      </td>
                      <td className="py-3 px-4 font-mono text-sm">
                        {candidate.right_record_id?.substring(0, 8) || '-'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        {candidate.score ? `${(candidate.score * 100).toFixed(0)}%` : '-'}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`rounded-full px-2 py-1 text-xs ${getStatusColor(candidate.decision_status)}`}>
                          {candidate.decision_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-sm text-muted-foreground mt-4">
                Review these candidates on the Exceptions page to approve or reject them.
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8">
              <HelpCircle className="h-8 w-8 text-muted-foreground mb-2" />
              <p className="text-muted-foreground">No candidates needing review</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Unmatched Records */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-red-500" />
            Unmatched Records ({unmatched?.length || 0})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {unmatched?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-4 font-medium">Record ID</th>
                    <th className="text-right py-3 px-4 font-medium">Amount</th>
                    <th className="text-left py-3 px-4 font-medium">Date</th>
                    <th className="text-left py-3 px-4 font-medium">Reference</th>
                    <th className="text-left py-3 px-4 font-medium">Description</th>
                    <th className="text-left py-3 px-4 font-medium">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {unmatched.map((record: any, index: number) => (
                    <tr key={record.id || index} className="border-b hover:bg-muted/50">
                      <td className="py-3 px-4 font-mono text-sm">
                        {record.external_record_id || '-'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        {record.amount ? formatCurrency(record.amount) : '-'}
                      </td>
                      <td className="py-3 px-4">
                        {record.record_date || '-'}
                      </td>
                      <td className="py-3 px-4 font-mono text-sm">
                        {record.reference_code || '-'}
                      </td>
                      <td className="py-3 px-4 text-sm truncate max-w-xs">
                        {record.description || '-'}
                      </td>
                      <td className="py-3 px-4">
                        <span className="rounded-full bg-red-100 text-red-800 px-2 py-1 text-xs">
                          {record.reason_code || 'no_match'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8">
              <CheckCircle className="h-8 w-8 text-green-500 mb-2" />
              <p className="text-muted-foreground">All records matched!</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

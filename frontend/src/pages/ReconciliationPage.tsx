import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reconciliationApi, sourcesApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatDateTime, getStatusColor, formatNumber, formatPercentage } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'
import { Play, GitCompare, CheckCircle, XCircle, Clock, Search } from 'lucide-react'

export function ReconciliationPage() {
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [formType, setFormType] = useState<'reconcile' | 'duplicates'>('reconcile')
  const [newRunName, setNewRunName] = useState('')
  const [leftSourceId, setLeftSourceId] = useState('')
  const [rightSourceId, setRightSourceId] = useState('')
  const [singleSourceId, setSingleSourceId] = useState('')
  const [dateTolerance, setDateTolerance] = useState('3')
  const [amountTolerance, setAmountTolerance] = useState('1')
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: sources } = useQuery({
    queryKey: ['sources'],
    queryFn: () => sourcesApi.list(true),
  })

  const { data: runs, isLoading } = useQuery({
    queryKey: ['reconciliation-runs'],
    queryFn: () => reconciliationApi.listRuns({ limit: 50 }),
  })

  const createReconciliationMutation = useMutation({
    mutationFn: (data: { name: string; left_source_id: string; right_source_id: string; parameters?: any }) =>
      reconciliationApi.createRun(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reconciliation-runs'] })
      resetForm()
      toast({ title: 'Reconciliation run started' })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to start reconciliation',
        description: error.response?.data?.detail || 'An error occurred',
        variant: 'destructive',
      })
    },
  })

  const createDuplicateMutation = useMutation({
    mutationFn: (data: { name: string; source_id: string }) =>
      reconciliationApi.createDuplicateDetection(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reconciliation-runs'] })
      resetForm()
      toast({ title: 'Duplicate detection started' })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to start duplicate detection',
        description: error.response?.data?.detail || 'An error occurred',
        variant: 'destructive',
      })
    },
  })

  const resetForm = () => {
    setShowCreateForm(false)
    setNewRunName('')
    setLeftSourceId('')
    setRightSourceId('')
    setSingleSourceId('')
    setDateTolerance('3')
    setAmountTolerance('1')
  }

  const handleCreateRun = (e: React.FormEvent) => {
    e.preventDefault()
    if (formType === 'reconcile') {
      if (newRunName.trim() && leftSourceId && rightSourceId) {
        createReconciliationMutation.mutate({
          name: newRunName,
          left_source_id: leftSourceId,
          right_source_id: rightSourceId,
          parameters: {
            date_tolerance_days: parseInt(dateTolerance) || 3,
            amount_tolerance_percent: parseFloat(amountTolerance) || 1,
          },
        })
      }
    } else {
      if (newRunName.trim() && singleSourceId) {
        createDuplicateMutation.mutate({
          name: newRunName,
          source_id: singleSourceId,
        })
      }
    }
  }

  const isPending = createReconciliationMutation.isPending || createDuplicateMutation.isPending

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <Clock className="h-4 w-4 text-yellow-500" />
    }
  }

  const calculateMatchRate = (run: any) => {
    const total = (run.total_left_records || 0) + (run.total_right_records || 0)
    const matched = (run.total_matched || 0) * 2
    return total > 0 ? matched / total : 0
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Reconciliation</h1>
          <p className="text-muted-foreground">
            Run and monitor reconciliation processes
          </p>
        </div>
        <Button onClick={() => setShowCreateForm(true)}>
          <Play className="mr-2 h-4 w-4" />
          New Run
        </Button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <Card>
          <CardHeader>
            <CardTitle>
              {formType === 'reconcile' ? 'Start New Reconciliation Run' : 'Start Duplicate Detection'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4 mb-6">
              <Button
                type="button"
                variant={formType === 'reconcile' ? 'default' : 'outline'}
                onClick={() => setFormType('reconcile')}
              >
                <GitCompare className="mr-2 h-4 w-4" />
                Cross-Source Reconciliation
              </Button>
              <Button
                type="button"
                variant={formType === 'duplicates' ? 'default' : 'outline'}
                onClick={() => setFormType('duplicates')}
              >
                <Search className="mr-2 h-4 w-4" />
                Duplicate Detection
              </Button>
            </div>

            <form onSubmit={handleCreateRun} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Run Name</Label>
                <Input
                  id="name"
                  value={newRunName}
                  onChange={(e) => setNewRunName(e.target.value)}
                  placeholder={formType === 'reconcile'
                    ? 'e.g., March 2024 Bank vs Ledger Reconciliation'
                    : 'e.g., March 2024 Duplicate Check'
                  }
                  required
                />
              </div>

              {formType === 'reconcile' ? (
                <>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="leftSource">Left Source (Primary)</Label>
                      <select
                        id="leftSource"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        value={leftSourceId}
                        onChange={(e) => setLeftSourceId(e.target.value)}
                        required
                      >
                        <option value="">Select source...</option>
                        {sources?.map((source: any) => (
                          <option key={source.id} value={source.id}>
                            {source.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="rightSource">Right Source (Secondary)</Label>
                      <select
                        id="rightSource"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        value={rightSourceId}
                        onChange={(e) => setRightSourceId(e.target.value)}
                        required
                      >
                        <option value="">Select source...</option>
                        {sources?.filter((s: any) => s.id !== leftSourceId).map((source: any) => (
                          <option key={source.id} value={source.id}>
                            {source.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="dateTolerance">Date Tolerance (days)</Label>
                      <Input
                        id="dateTolerance"
                        type="number"
                        min="0"
                        max="30"
                        value={dateTolerance}
                        onChange={(e) => setDateTolerance(e.target.value)}
                        placeholder="e.g., 3"
                      />
                      <p className="text-xs text-muted-foreground">
                        Allow dates to differ by ± this many days
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="amountTolerance">Amount Tolerance (%)</Label>
                      <Input
                        id="amountTolerance"
                        type="number"
                        min="0"
                        max="100"
                        step="0.1"
                        value={amountTolerance}
                        onChange={(e) => setAmountTolerance(e.target.value)}
                        placeholder="e.g., 1"
                      />
                      <p className="text-xs text-muted-foreground">
                        Allow amounts to differ by ± this percentage
                      </p>
                    </div>
                  </div>
                </>
              ) : (
                <div className="space-y-2">
                  <Label htmlFor="singleSource">Source System</Label>
                  <select
                    id="singleSource"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={singleSourceId}
                    onChange={(e) => setSingleSourceId(e.target.value)}
                    required
                  >
                    <option value="">Select source...</option>
                    {sources?.map((source: any) => (
                      <option key={source.id} value={source.id}>
                        {source.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex gap-2">
                <Button type="submit" disabled={isPending}>
                  {isPending ? 'Starting...' : 'Start Run'}
                </Button>
                <Button type="button" variant="outline" onClick={resetForm}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Runs List */}
      <Card>
        <CardHeader>
          <CardTitle>Reconciliation Runs</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading...</div>
          ) : runs?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-4 font-medium">Name</th>
                    <th className="text-left py-3 px-4 font-medium">Status</th>
                    <th className="text-right py-3 px-4 font-medium">Left Records</th>
                    <th className="text-right py-3 px-4 font-medium">Right Records</th>
                    <th className="text-right py-3 px-4 font-medium">Matched</th>
                    <th className="text-right py-3 px-4 font-medium">Match Rate</th>
                    <th className="text-left py-3 px-4 font-medium">Created</th>
                    <th className="text-left py-3 px-4 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run: any) => (
                    <tr key={run.id} className="border-b hover:bg-muted/50">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <GitCompare className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{run.name}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(run.status)}
                          <span className={`rounded-full px-2 py-1 text-xs ${getStatusColor(run.status)}`}>
                            {run.status}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right">{formatNumber(run.total_left_records || 0)}</td>
                      <td className="py-3 px-4 text-right">{formatNumber(run.total_right_records || 0)}</td>
                      <td className="py-3 px-4 text-right text-green-600">
                        {formatNumber(run.total_matched || 0)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        {formatPercentage(calculateMatchRate(run))}
                      </td>
                      <td className="py-3 px-4 text-muted-foreground">
                        {formatDateTime(run.created_at)}
                      </td>
                      <td className="py-3 px-4">
                        <Button size="sm" variant="outline">
                          View Details
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12">
              <GitCompare className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">No reconciliation runs yet</h3>
              <p className="text-muted-foreground mb-4">
                Start a new run to begin reconciling your data
              </p>
              <Button onClick={() => setShowCreateForm(true)}>
                <Play className="mr-2 h-4 w-4" />
                New Run
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { reconciliationApi, exceptionsApi, ingestionApi, anomalyApi } from '@/lib/api'
import { formatNumber, formatPercentage, getStatusColor } from '@/lib/utils'
import { Link } from 'react-router-dom'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Legend,
} from 'recharts'
import {
  CheckCircle,
  AlertTriangle,
  Clock,
  TrendingUp,
  Upload,
  AlertCircle,
  ArrowRight,
  Activity,
  FileWarning,
  RefreshCw,
} from 'lucide-react'

const COLORS = ['#22c55e', '#eab308', '#ef4444', '#3b82f6', '#8b5cf6', '#ec4899']
const EXCEPTION_COLORS: Record<string, string> = {
  amount_mismatch: '#ef4444',
  date_mismatch: '#f97316',
  missing_counter_entry: '#eab308',
  low_confidence_candidate: '#3b82f6',
  duplicate_suspected: '#8b5cf6',
  anomaly_detected: '#ec4899',
}

export function DashboardPage() {
  const { data: runs } = useQuery({
    queryKey: ['reconciliation-runs'],
    queryFn: () => reconciliationApi.listRuns({ limit: 20 }),
  })

  const { data: exceptions } = useQuery({
    queryKey: ['exceptions-all'],
    queryFn: () => exceptionsApi.list({ limit: 100 }),
  })

  const { data: jobs } = useQuery({
    queryKey: ['ingestion-jobs'],
    queryFn: () => ingestionApi.listJobs({ limit: 20 }),
  })

  const { data: anomalies } = useQuery({
    queryKey: ['anomalies'],
    queryFn: () => anomalyApi.list({ limit: 50 }),
  })

  // Calculate summary stats
  const totalReconciliations = runs?.length || 0
  const openExceptions = exceptions?.items?.filter((e: any) => e.status === 'open' || e.status === 'in_review').length || 0
  const totalAnomalies = anomalies?.items?.filter((a: any) => !a.reviewed).length || 0
  const recentIngestions = jobs?.length || 0

  // Calculate average match rate from recent runs
  const completedRuns = runs?.filter((r: any) => r.status === 'completed') || []
  const avgMatchRate = completedRuns.length
    ? completedRuns.reduce((acc: number, run: any) => {
        const total = (run.total_left_records || 0) + (run.total_right_records || 0)
        const matched = (run.total_matched || 0) * 2
        return acc + (total > 0 ? matched / total : 0)
      }, 0) / completedRuns.length
    : 0

  // Group exceptions by type
  const exceptionsByType = (exceptions?.items || []).reduce((acc: Record<string, number>, exc: any) => {
    const type = exc.exception_type || 'other'
    acc[type] = (acc[type] || 0) + 1
    return acc
  }, {})

  const exceptionChartData = Object.entries(exceptionsByType).map(([name, value]) => ({
    name: name.replace(/_/g, ' '),
    value,
    color: EXCEPTION_COLORS[name] || '#94a3b8',
  }))

  // Group exceptions by status
  const exceptionsByStatus = (exceptions?.items || []).reduce((acc: Record<string, number>, exc: any) => {
    const status = exc.status || 'unknown'
    acc[status] = (acc[status] || 0) + 1
    return acc
  }, {})

  const statusChartData = [
    { name: 'Open', value: exceptionsByStatus['open'] || 0, color: '#ef4444' },
    { name: 'In Review', value: exceptionsByStatus['in_review'] || 0, color: '#eab308' },
    { name: 'Resolved', value: exceptionsByStatus['resolved'] || 0, color: '#22c55e' },
    { name: 'Dismissed', value: exceptionsByStatus['dismissed'] || 0, color: '#94a3b8' },
  ].filter(d => d.value > 0)

  // Reconciliation runs trend (last 7)
  const runsTrend = (runs?.slice(0, 7) || []).reverse().map((run: any, idx: number) => ({
    name: `Run ${idx + 1}`,
    matched: run.total_matched || 0,
    unmatched: run.total_unmatched || 0,
    exceptions: run.total_exceptions || 0,
  }))

  // Ingestion job status
  const jobsByStatus = (jobs || []).reduce((acc: Record<string, number>, job: any) => {
    const status = job.status || 'unknown'
    acc[status] = (acc[status] || 0) + 1
    return acc
  }, {})

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of your reconciliation operations
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link to="/reconciliation">
              View Runs
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Match Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {formatPercentage(avgMatchRate)}
            </div>
            <p className="text-xs text-muted-foreground">
              From {completedRuns.length} completed runs
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Open Exceptions</CardTitle>
            <AlertTriangle className="h-4 w-4 text-orange-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">{formatNumber(openExceptions)}</div>
            <p className="text-xs text-muted-foreground">
              Requiring attention
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Anomalies</CardTitle>
            <FileWarning className="h-4 w-4 text-purple-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">{formatNumber(totalAnomalies)}</div>
            <p className="text-xs text-muted-foreground">
              Unreviewed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recon Runs</CardTitle>
            <CheckCircle className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(totalReconciliations)}</div>
            <p className="text-xs text-muted-foreground">
              Total runs
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Ingestions</CardTitle>
            <Upload className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(recentIngestions)}</div>
            <p className="text-xs text-muted-foreground">
              Data imports
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 1 */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Reconciliation Trend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              {runsTrend.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={runsTrend}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="name" className="text-xs" />
                    <YAxis className="text-xs" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--background))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '6px',
                      }}
                    />
                    <Legend />
                    <Bar dataKey="matched" fill="#22c55e" name="Matched" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="unmatched" fill="#ef4444" name="Unmatched" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="exceptions" fill="#eab308" name="Exceptions" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <p>No reconciliation data yet</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5" />
              Exceptions by Type
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              {exceptionChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={exceptionChartData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                      dataKey="value"
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      labelLine={false}
                    >
                      {exceptionChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--background))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '6px',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <p>No exceptions to display</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Exception Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              {statusChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={statusChartData}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {statusChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--background))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '6px',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <p>No exception data</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Ingestion Jobs Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {Object.entries(jobsByStatus).length > 0 ? (
                Object.entries(jobsByStatus).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`w-3 h-3 rounded-full ${
                        status === 'completed' ? 'bg-green-500' :
                        status === 'running' ? 'bg-blue-500' :
                        status === 'failed' ? 'bg-red-500' :
                        'bg-gray-400'
                      }`} />
                      <span className="capitalize">{status}</span>
                    </div>
                    <span className="font-medium">{count as number}</span>
                  </div>
                ))
              ) : (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <p>No ingestion jobs yet</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Recent Reconciliation Runs</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link to="/reconciliation">
              View All
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {runs?.slice(0, 5).map((run: any) => (
              <div
                key={run.id}
                className="flex items-center justify-between border-b pb-4 last:border-0 last:pb-0"
              >
                <div>
                  <p className="font-medium">{run.name || 'Reconciliation Run'}</p>
                  <p className="text-sm text-muted-foreground">
                    {run.created_at && new Date(run.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusColor(run.status)}`}>
                    {run.status === 'completed' && <CheckCircle className="h-3 w-3" />}
                    {run.status === 'processing' && <RefreshCw className="h-3 w-3 animate-spin" />}
                    {run.status}
                  </span>
                  <div className="text-right text-sm">
                    <p className="text-green-600">{run.total_matched || 0} matched</p>
                    <p className="text-muted-foreground">{run.total_unmatched || 0} unmatched</p>
                  </div>
                </div>
              </div>
            ))}
            {(!runs || runs.length === 0) && (
              <div className="text-center py-8 text-muted-foreground">
                <Activity className="h-8 w-8 mx-auto mb-2" />
                <p>No reconciliation runs yet</p>
                <Button variant="outline" size="sm" className="mt-2" asChild>
                  <Link to="/reconciliation">Start a Run</Link>
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

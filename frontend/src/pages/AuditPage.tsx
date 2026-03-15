import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { auditApi } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTime } from '@/lib/utils'
import { History, User, FileText, Database, GitCompare, AlertTriangle } from 'lucide-react'

const getEntityIcon = (entityType: string) => {
  const icons: Record<string, any> = {
    user: User,
    source_system: Database,
    ingestion_job: FileText,
    reconciliation_run: GitCompare,
    exception: AlertTriangle,
  }
  const Icon = icons[entityType] || History
  return <Icon className="h-4 w-4" />
}

const getActionColor = (actionType: string) => {
  if (actionType.includes('created') || actionType.includes('completed')) {
    return 'text-green-600'
  }
  if (actionType.includes('failed') || actionType.includes('deleted')) {
    return 'text-red-600'
  }
  if (actionType.includes('updated') || actionType.includes('started')) {
    return 'text-blue-600'
  }
  return 'text-gray-600'
}

export function AuditPage() {
  const [selectedEntityType, setSelectedEntityType] = useState<string>('')
  const [selectedActionType, setSelectedActionType] = useState<string>('')

  const { data: auditData, isLoading } = useQuery({
    queryKey: ['audit-logs', selectedEntityType, selectedActionType],
    queryFn: () =>
      auditApi.list({
        entity_type: selectedEntityType || undefined,
        action_type: selectedActionType || undefined,
        limit: 100,
      }),
  })

  const logs = auditData?.items || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Audit Log</h1>
        <p className="text-muted-foreground">
          Track all system activity and changes
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <select
              className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={selectedEntityType}
              onChange={(e) => setSelectedEntityType(e.target.value)}
            >
              <option value="">All Entities</option>
              <option value="user">Users</option>
              <option value="source_system">Source Systems</option>
              <option value="ingestion_job">Ingestion Jobs</option>
              <option value="reconciliation_run">Reconciliation Runs</option>
              <option value="exception">Exceptions</option>
              <option value="report">Reports</option>
            </select>
            <select
              className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={selectedActionType}
              onChange={(e) => setSelectedActionType(e.target.value)}
            >
              <option value="">All Actions</option>
              <option value="created">Created</option>
              <option value="updated">Updated</option>
              <option value="deleted">Deleted</option>
              <option value="login">Login</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Audit Log */}
      <Card>
        <CardHeader>
          <CardTitle>Activity Log</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading...</div>
          ) : logs.length > 0 ? (
            <div className="space-y-4">
              {logs.map((log: any) => (
                <div
                  key={log.id}
                  className="flex items-start gap-4 border-b pb-4 last:border-0"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                    {getEntityIcon(log.entity_type)}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`font-medium ${getActionColor(log.action_type)}`}>
                        {log.action_type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-muted-foreground">on</span>
                      <span className="font-medium">{log.entity_type.replace(/_/g, ' ')}</span>
                    </div>
                    {log.entity_id && (
                      <p className="text-sm text-muted-foreground">
                        ID: {log.entity_id.slice(0, 8)}...
                      </p>
                    )}
                    {log.metadata_json && Object.keys(log.metadata_json).length > 0 && (
                      <div className="mt-2 text-sm text-muted-foreground">
                        <pre className="bg-muted rounded p-2 overflow-x-auto">
                          {JSON.stringify(log.metadata_json, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                  <div className="text-right text-sm text-muted-foreground">
                    <p>{formatDateTime(log.created_at)}</p>
                    {log.actor_user_id && (
                      <p className="flex items-center gap-1 justify-end">
                        <User className="h-3 w-3" />
                        {log.actor_user_id.slice(0, 8)}...
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12">
              <History className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">No audit logs found</h3>
              <p className="text-muted-foreground">
                Activity will be recorded here as you use the system
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

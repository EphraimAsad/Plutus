import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sourcesApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatDateTime, getStatusColor } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'
import { Plus, Database, Settings } from 'lucide-react'

export function SourcesPage() {
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newSource, setNewSource] = useState({ name: '', source_type: 'csv', description: '' })
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: sources, isLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: () => sourcesApi.list(false),
  })

  const createMutation = useMutation({
    mutationFn: (data: any) => sourcesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] })
      setShowCreateForm(false)
      setNewSource({ name: '', source_type: 'csv', description: '' })
      toast({ title: 'Source created successfully' })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to create source',
        description: error.response?.data?.detail || 'An error occurred',
        variant: 'destructive',
      })
    },
  })

  const handleCreateSource = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(newSource)
  }

  if (isLoading) {
    return <div className="flex items-center justify-center p-8">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Source Systems</h1>
          <p className="text-muted-foreground">
            Configure data sources for reconciliation
          </p>
        </div>
        <Button onClick={() => setShowCreateForm(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Source
        </Button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <Card>
          <CardHeader>
            <CardTitle>Create New Source</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateSource} className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Name</Label>
                  <Input
                    id="name"
                    value={newSource.name}
                    onChange={(e) => setNewSource({ ...newSource, name: e.target.value })}
                    placeholder="e.g., Bank Transactions"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="source_type">Type</Label>
                  <select
                    id="source_type"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={newSource.source_type}
                    onChange={(e) => setNewSource({ ...newSource, source_type: e.target.value })}
                  >
                    <option value="csv">CSV</option>
                    <option value="xlsx">Excel (XLSX)</option>
                  </select>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Input
                  id="description"
                  value={newSource.description}
                  onChange={(e) => setNewSource({ ...newSource, description: e.target.value })}
                  placeholder="Optional description"
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Creating...' : 'Create Source'}
                </Button>
                <Button type="button" variant="outline" onClick={() => setShowCreateForm(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Sources List */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {sources?.map((source: any) => (
          <Card key={source.id}>
            <CardHeader className="flex flex-row items-start justify-between space-y-0">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Database className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-lg">{source.name}</CardTitle>
                  <p className="text-sm text-muted-foreground">{source.source_type.toUpperCase()}</p>
                </div>
              </div>
              <span className={`rounded-full px-2 py-1 text-xs ${getStatusColor(source.is_active ? 'active' : 'inactive')}`}>
                {source.is_active ? 'Active' : 'Inactive'}
              </span>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                {source.description || 'No description'}
              </p>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  Schema v{source.active_mapping_version || 'None'}
                </span>
                <span className="text-muted-foreground">
                  Created {formatDateTime(source.created_at)}
                </span>
              </div>
              <div className="mt-4 flex gap-2">
                <Button size="sm" variant="outline">
                  <Settings className="mr-1 h-3 w-3" />
                  Configure
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {(!sources || sources.length === 0) && !showCreateForm && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Database className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">No source systems configured</h3>
            <p className="text-muted-foreground mb-4">
              Get started by adding your first data source
            </p>
            <Button onClick={() => setShowCreateForm(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Source
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

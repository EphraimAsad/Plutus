import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sourcesApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatDateTime, getStatusColor } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'
import { Plus, Database, Settings, X, Trash2 } from 'lucide-react'

export function SourcesPage() {
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newSource, setNewSource] = useState({ name: '', source_type: 'csv', description: '' })
  const [selectedSource, setSelectedSource] = useState<any>(null)
  const [showMappingForm, setShowMappingForm] = useState(false)
  const [mapping, setMapping] = useState({
    external_record_id: '',
    amount: '',
    record_date: '',
    description: '',
    reference_code: '',
  })
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

  const mappingMutation = useMutation({
    mutationFn: (data: { sourceId: string; mapping: any }) =>
      sourcesApi.createSchemaMapping(data.sourceId, {
        mapping_json: {
          fields: data.mapping,
          date_format: '%Y-%m-%d',
          decimal_separator: '.',
          skip_rows: 0,
        },
        is_active: true,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] })
      setShowMappingForm(false)
      setSelectedSource(null)
      setMapping({ external_record_id: '', amount: '', record_date: '', description: '', reference_code: '' })
      toast({ title: 'Schema mapping saved successfully' })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to save schema mapping',
        description: error.response?.data?.detail || 'An error occurred',
        variant: 'destructive',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => sourcesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] })
      toast({ title: 'Source deleted successfully' })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to delete source',
        description: error.response?.data?.detail || 'An error occurred',
        variant: 'destructive',
      })
    },
  })

  const handleCreateSource = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(newSource)
  }

  const handleSaveMapping = (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedSource) return

    // Reverse the mapping: backend expects {source_column: canonical_field}
    // but form collects {canonical_field: source_column}
    const reversedMapping: Record<string, string> = {}
    for (const [canonicalField, sourceColumn] of Object.entries(mapping)) {
      if (sourceColumn) {
        reversedMapping[sourceColumn] = canonicalField
      }
    }

    mappingMutation.mutate({ sourceId: selectedSource.id, mapping: reversedMapping })
  }

  const openMappingForm = (source: any) => {
    setSelectedSource(source)
    setShowMappingForm(true)
  }

  const handleDelete = (source: any) => {
    if (confirm(`Delete source "${source.name}"? This will also delete all related data.`)) {
      deleteMutation.mutate(source.id)
    }
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

      {/* Schema Mapping Form */}
      {showMappingForm && selectedSource && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Configure Schema Mapping: {selectedSource.name}</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => { setShowMappingForm(false); setSelectedSource(null); }}>
              <X className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSaveMapping} className="space-y-4">
              <p className="text-sm text-muted-foreground mb-4">
                Enter the column names from your CSV/Excel file that correspond to each field.
              </p>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="map_external_record_id">Record ID Column *</Label>
                  <Input
                    id="map_external_record_id"
                    value={mapping.external_record_id}
                    onChange={(e) => setMapping({ ...mapping, external_record_id: e.target.value })}
                    placeholder="e.g., transaction_id, entry_id"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="map_amount">Amount Column</Label>
                  <Input
                    id="map_amount"
                    value={mapping.amount}
                    onChange={(e) => setMapping({ ...mapping, amount: e.target.value })}
                    placeholder="e.g., amount"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="map_record_date">Date Column *</Label>
                  <Input
                    id="map_record_date"
                    value={mapping.record_date}
                    onChange={(e) => setMapping({ ...mapping, record_date: e.target.value })}
                    placeholder="e.g., date, posting_date"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="map_description">Description Column</Label>
                  <Input
                    id="map_description"
                    value={mapping.description}
                    onChange={(e) => setMapping({ ...mapping, description: e.target.value })}
                    placeholder="e.g., description, memo"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="map_reference_code">Reference Column</Label>
                  <Input
                    id="map_reference_code"
                    value={mapping.reference_code}
                    onChange={(e) => setMapping({ ...mapping, reference_code: e.target.value })}
                    placeholder="e.g., reference, ref_number"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={mappingMutation.isPending}>
                  {mappingMutation.isPending ? 'Saving...' : 'Save Mapping'}
                </Button>
                <Button type="button" variant="outline" onClick={() => { setShowMappingForm(false); setSelectedSource(null); }}>
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
                <Button size="sm" variant="outline" onClick={() => openMappingForm(source)}>
                  <Settings className="mr-1 h-3 w-3" />
                  Configure
                </Button>
                <Button size="sm" variant="outline" className="text-red-600 hover:text-red-700 hover:bg-red-50" onClick={() => handleDelete(source)}>
                  <Trash2 className="mr-1 h-3 w-3" />
                  Delete
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

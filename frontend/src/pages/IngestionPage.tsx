import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ingestionApi, sourcesApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatDateTime, getStatusColor, formatNumber } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'
import { Upload, FileText, CheckCircle, XCircle, Clock, Trash2 } from 'lucide-react'

export function IngestionPage() {
  const [selectedSource, setSelectedSource] = useState<string>('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: sources } = useQuery({
    queryKey: ['sources'],
    queryFn: () => sourcesApi.list(true),
  })

  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['ingestion-jobs'],
    queryFn: () => ingestionApi.listJobs({ limit: 50 }),
  })

  const uploadMutation = useMutation({
    mutationFn: ({ sourceId, file }: { sourceId: string; file: File }) =>
      ingestionApi.upload(sourceId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ingestion-jobs'] })
      setSelectedFile(null)
      setSelectedSource('')
      toast({ title: 'File uploaded successfully' })
    },
    onError: (error: any) => {
      toast({
        title: 'Upload failed',
        description: error.response?.data?.detail || 'An error occurred',
        variant: 'destructive',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => ingestionApi.deleteJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ingestion-jobs'] })
      toast({ title: 'Job deleted successfully' })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to delete job',
        description: error.response?.data?.detail || 'An error occurred',
        variant: 'destructive',
      })
    },
  })

  const handleUpload = () => {
    if (selectedSource && selectedFile) {
      uploadMutation.mutate({ sourceId: selectedSource, file: selectedFile })
    }
  }

  const handleDeleteJob = (job: any) => {
    if (confirm(`Delete job "${job.file_name}"? This will also delete all related records.`)) {
      deleteMutation.mutate(job.id)
    }
  }

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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Data Ingestion</h1>
        <p className="text-muted-foreground">
          Upload and process data files
        </p>
      </div>

      {/* Upload Form */}
      <Card>
        <CardHeader>
          <CardTitle>Upload File</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="source">Source System</Label>
              <select
                id="source"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={selectedSource}
                onChange={(e) => setSelectedSource(e.target.value)}
              >
                <option value="">Select a source...</option>
                {sources?.map((source: any) => (
                  <option key={source.id} value={source.id}>
                    {source.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="file">File</Label>
              <Input
                id="file"
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              />
            </div>
            <div className="flex items-end">
              <Button
                onClick={handleUpload}
                disabled={!selectedSource || !selectedFile || uploadMutation.isPending}
                className="w-full"
              >
                <Upload className="mr-2 h-4 w-4" />
                {uploadMutation.isPending ? 'Uploading...' : 'Upload'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Ingestion Jobs */}
      <Card>
        <CardHeader>
          <CardTitle>Ingestion Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          {jobsLoading ? (
            <div className="text-center py-8">Loading...</div>
          ) : jobs?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-4 font-medium">File</th>
                    <th className="text-left py-3 px-4 font-medium">Status</th>
                    <th className="text-right py-3 px-4 font-medium">Rows</th>
                    <th className="text-right py-3 px-4 font-medium">Valid</th>
                    <th className="text-right py-3 px-4 font-medium">Invalid</th>
                    <th className="text-left py-3 px-4 font-medium">Created</th>
                    <th className="text-left py-3 px-4 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job: any) => (
                    <tr key={job.id} className="border-b hover:bg-muted/50">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                          <span className="truncate max-w-xs">{job.file_name || 'Unknown'}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(job.status)}
                          <span className={`rounded-full px-2 py-1 text-xs ${getStatusColor(job.status)}`}>
                            {job.status}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right">{formatNumber(job.rows_received)}</td>
                      <td className="py-3 px-4 text-right text-green-600">
                        {formatNumber(job.rows_valid)}
                      </td>
                      <td className="py-3 px-4 text-right text-red-600">
                        {formatNumber(job.rows_invalid)}
                      </td>
                      <td className="py-3 px-4 text-muted-foreground">
                        {formatDateTime(job.created_at)}
                      </td>
                      <td className="py-3 px-4">
                        <Button size="sm" variant="outline" className="text-red-600 hover:text-red-700 hover:bg-red-50" onClick={() => handleDeleteJob(job)}>
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12">
              <Upload className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">No ingestion jobs yet</h3>
              <p className="text-muted-foreground">
                Upload a file to get started
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export type BusinessFlowStage = {
  id: string
  label: string
  status: 'waiting' | 'running' | 'done' | 'blocked'
}

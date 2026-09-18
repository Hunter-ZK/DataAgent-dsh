import { requiresApproval, sanitizeArguments, touchesProdDb } from './policy.js'

export const name = 'agent3-guard'
export const inject = ['tools', 'approval']

interface GuardConfig { auditEndpoint?: string }

export function apply(ctx: any, config: GuardConfig = {}) {
  ctx.tools.guard((exec: any) => {
    if (touchesProdDb(exec)) return 'INV-S01/S02: dsh shell is forbidden from reaching production databases'
    return undefined
  })

  ctx.on('tools/pre-execute', async (exec: any, next: () => Promise<any>) => {
    if (!requiresApproval(exec)) return next()
    const outcome = await ctx.approval.request({ agent: exec.agent, toolName: exec.name, callId: exec.callId, reason: 'Agent3 write operation requires explicit human approval', signal: exec.signal })
    if (outcome === 'allowed-once') return next()
    return { kind: 'deny', reason: `approval failed closed: ${outcome}` }
  })

  ctx.on('tools/result', (exec: any, result: any) => {
    if (!config.auditEndpoint) return
    const payload = { sessionId: exec.agent?.sessionId ?? null, callId: exec.callId ?? null, toolName: exec.name, argumentsNorm: sanitizeArguments(exec.arguments), failed: Boolean(result?.isError ?? result?.error), createdAt: new Date().toISOString() }
    void fetch(config.auditEndpoint, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload) }).catch(() => undefined)
  })
}

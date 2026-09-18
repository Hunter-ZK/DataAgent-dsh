export interface ToolExecutionLike {
  name: string
  arguments?: Record<string, unknown>
}

const PROD_DB_PATTERNS = [/\bpsql\b/i, /\bmysql\b/i, /\bodps\b/i, /jdbc:/i, /prod(?:uction)?[_-]?(?:db|warehouse|dw)?/i]

export function touchesProdDb(exec: ToolExecutionLike): boolean {
  if (exec.name !== 'bash' && exec.name !== 'pwsh') return false
  const text = JSON.stringify(exec.arguments ?? {})
  return PROD_DB_PATTERNS.some((pattern) => pattern.test(text))
}

export function requiresApproval(exec: ToolExecutionLike): boolean {
  return exec.name === 'mcp__agent3__submit_ddl' || exec.name === 'mcp__agent3__register_verified_sql'
}

export function sanitizeArguments(args: Record<string, unknown> | undefined): Record<string, unknown> {
  const source = args ?? {}
  const output: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(source)) {
    if (/token|secret|password|credential|api[_-]?key/i.test(key)) output[key] = '[REDACTED]'
    else if (/sql/i.test(key) && typeof value === 'string') output[key] = { length: value.length, retained: false }
    else output[key] = value
  }
  return output
}

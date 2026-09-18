import assert from 'node:assert/strict'
import test from 'node:test'
import { requiresApproval, sanitizeArguments, touchesProdDb } from './policy.js'

test('blocks shell database clients', () => {
  assert.equal(touchesProdDb({ name: 'bash', arguments: { command: 'psql prod_db' } }), true)
  assert.equal(touchesProdDb({ name: 'bash', arguments: { command: 'pytest -q' } }), false)
})

test('approval surface is narrow', () => {
  assert.equal(requiresApproval({ name: 'mcp__agent3__submit_ddl' }), true)
  assert.equal(requiresApproval({ name: 'mcp__agent3__validate_sql' }), false)
})

test('audit sanitizer redacts credentials and raw SQL', () => {
  const value = sanitizeArguments({ apiKey: 'x', sql: 'select 1', table: 't' })
  assert.equal(value.apiKey, '[REDACTED]')
  assert.deepEqual(value.sql, { length: 8, retained: false })
  assert.equal(value.table, 't')
})

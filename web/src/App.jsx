import React, { useEffect, useMemo, useState } from 'react'

const api = async (path, options = {}) => {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || response.statusText)
  return response.json()
}

export default function App() {
  const [me, setMe] = useState(null)
  const [conversations, setConversations] = useState([])
  const [active, setActive] = useState(null)
  const [messages, setMessages] = useState([])
  const [events, setEvents] = useState([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)

  const refreshConversations = async () => setConversations(await api('/api/conversations'))
  useEffect(() => { api('/api/me').then(setMe); refreshConversations() }, [])
  useEffect(() => {
    if (!active) return
    api(`/api/conversations/${active}/messages`).then(setMessages)
    const source = new EventSource(`/api/conversations/${active}/stream`)
    const onEvent = (event) => {
      const data = JSON.parse(event.data)
      setEvents((items) => [...items.slice(-199), { id: event.lastEventId, ...data }])
      if (data.type === 'done') api(`/api/conversations/${active}/messages`).then(setMessages)
    }
    ;['thinking','tool_start','tool_result','sql','result_table','caveat','clarification_needed','scope_notice','refusal','error','done'].forEach((name) => source.addEventListener(name, onEvent))
    return () => source.close()
  }, [active])

  const createConversation = async () => {
    const record = await api('/api/conversations', { method: 'POST', body: JSON.stringify({ title: '新会话' }) })
    await refreshConversations(); setActive(record.id); setMessages([]); setEvents([])
  }
  const send = async () => {
    if (!active || !question.trim()) return
    setBusy(true)
    try {
      await api(`/api/conversations/${active}/messages`, { method: 'POST', body: JSON.stringify({ objective: question.trim() }) })
      setQuestion(''); setMessages(await api(`/api/conversations/${active}/messages`))
    } finally { setBusy(false) }
  }
  const clarification = useMemo(() => [...events].reverse().find((item) => item.type === 'clarification_needed'), [events])
  const answerClarification = async (answer) => {
    if (!clarification?.clarification_id) return
    await api(`/api/clarifications/${clarification.clarification_id}/answer`, { method: 'POST', body: JSON.stringify({ answer }) })
  }

  return <div className="shell">
    <aside>
      <div className="brand">DataAgent</div>
      <button onClick={createConversation}>＋ 新建会话</button>
      <div className="conversation-list">{conversations.map((item) => <button className={active === item.id ? 'active' : ''} key={item.id} onClick={() => { setActive(item.id); setEvents([]) }}>{item.title || '未命名会话'}</button>)}</div>
      <div className="identity">{me ? `${me.principal} · ${me.roles.join(', ') || 'user'}` : '身份加载中'}</div>
    </aside>
    <main>
      <header><h1>数据智能助手</h1><span>标准问数走确定性引擎，开放分析走本地 dsh</span></header>
      <section className="messages">
        {!active && <div className="empty">新建或选择一个会话开始。</div>}
        {messages.map((message) => <article key={message.id} className={`message ${message.role}`}><div className="role">{message.role === 'user' ? '你' : 'DataAgent'}</div><pre>{message.content.text || message.content.reason || (message.content.result ? JSON.stringify(message.content.result, null, 2) : message.content.sql || JSON.stringify(message.content, null, 2))}</pre></article>)}
        {clarification && <div className="clarification"><strong>{clarification.question}</strong><div>{(clarification.options || []).map((option) => <button key={option} onClick={() => answerClarification(option)}>{option}</button>)}</div></div>}
        {events.slice(-8).map((event, index) => <div className="event" key={`${event.id}-${index}`}><b>{event.type}</b> {event.text || event.tool || event.message || ''}</div>)}
      </section>
      <footer><textarea value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} placeholder="例如：2026年8月31日深圳贷款余额是多少？"/><button disabled={!active || busy} onClick={send}>{busy ? '发送中' : '发送'}</button></footer>
    </main>
  </div>
}

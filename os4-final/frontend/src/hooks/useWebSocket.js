import { useEffect, useRef, useState } from 'react'

const BACKOFF = [1000, 2000, 4000, 8000, 16000]

export function useWebSocket(token, onEvent) {
  const [status, setStatus]  = useState('disconnected')
  const wsRef      = useRef(null)
  const onEventRef = useRef(onEvent)
  const attemptRef = useRef(0)
  const deadRef    = useRef(false)
  const timerRef   = useRef(null)

  useEffect(() => { onEventRef.current = onEvent }, [onEvent])

  useEffect(() => {
    if (!token) return
    deadRef.current = false

    function connect() {
      if (deadRef.current) return
      setStatus('connecting')

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws?token=${token}`)
      wsRef.current = ws

      ws.onopen = () => {
        if (deadRef.current) { ws.close(); return }
        setStatus('connected')
        attemptRef.current = 0
      }

      ws.onmessage = (evt) => {
        if (deadRef.current) return
        try { onEventRef.current(JSON.parse(evt.data)) }
        catch (e) { console.warn('[WS] parse error', e) }
      }

      ws.onerror = () => {
        if (!deadRef.current) setStatus('error')
      }

      ws.onclose = () => {
        if (deadRef.current) return
        setStatus('disconnected')
        const delay = BACKOFF[Math.min(attemptRef.current, BACKOFF.length - 1)]
        attemptRef.current++
        timerRef.current = setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      deadRef.current = true
      clearTimeout(timerRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
      setStatus('disconnected')
    }
  }, [token])

  return { status }
}

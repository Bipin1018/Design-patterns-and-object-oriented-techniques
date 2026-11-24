/**
 * Live events from the backend.
 *
 * Phase 11 stub: subscribeRealtime does nothing, so the dashboard keeps polling.
 * Phase 12 replaces the body with the dashboard WebSocket. Components that
 * already subscribe (EventFeed does) will then get events without changes.
 */

/** One message, e.g. { type: 'alert.created', payload: {...} }. */
export type RealtimeEvent = {
  type: string
  payload: unknown
}

/** Start listening. Returns a function that stops listening. */
export function subscribeRealtime(handler: (event: RealtimeEvent) => void): () => void {
  void handler // Phase 12: open the socket and call handler for each message.
  return () => {
    // Phase 12: close the socket.
  }
}
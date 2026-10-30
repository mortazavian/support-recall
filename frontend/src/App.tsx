import { useCallback, useEffect, useReducer, useState } from 'react'
import type { ReactNode } from 'react'
import { fetchHealth } from './api'
import { strings } from './strings'

type Page = 'chat' | 'knowledge' | 'settings'
type Connection = 'checking' | 'connected' | 'disconnected'
type ConnectionAction = { type: 'checking' } | { type: 'resolved'; connected: boolean }

function connectionReducer(_state: Connection, action: ConnectionAction): Connection {
  if (action.type === 'checking') return 'checking'
  return action.connected ? 'connected' : 'disconnected'
}

const navigation: { id: Page; label: string; icon: string }[] = [
  { id: 'chat', label: strings.navigation.chat, icon: 'chat' },
  { id: 'knowledge', label: strings.navigation.knowledge, icon: 'library' },
  { id: 'settings', label: strings.navigation.settings, icon: 'settings' },
]

function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    chat: <><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l-3 2v-7.5a7.5 7.5 0 1 1 15 0Z" /><path d="M8 11h.01M12 11h.01M16 11h.01" /></>,
    library: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21V5.5Z" /><path d="M4 6v15M8 7h8M8 11h8" /></>,
    settings: <><path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" /><path d="m19.4 15 .1.1a1.8 1.8 0 0 1-2.5 2.5l-.1-.1a1.8 1.8 0 0 0-3 .9v.2a1.8 1.8 0 0 1-3.6 0v-.2a1.8 1.8 0 0 0-3-.9l-.1.1a1.8 1.8 0 0 1-2.5-2.5l.1-.1a1.8 1.8 0 0 0-.9-3h-.2a1.8 1.8 0 0 1 0-3.6h.2a1.8 1.8 0 0 0 .9-3l-.1-.1a1.8 1.8 0 0 1 2.5-2.5l.1.1a1.8 1.8 0 0 0 3-.9v-.2a1.8 1.8 0 0 1 3.6 0v.2a1.8 1.8 0 0 0 3 .9l.1-.1a1.8 1.8 0 0 1 2.5 2.5l-.1.1a1.8 1.8 0 0 0 .9 3h.2a1.8 1.8 0 0 1 0 3.6h-.2a1.8 1.8 0 0 0-.9 3Z" /></>,
    sparkle: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" /><path d="m19 15 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z" /></>,
    arrow: <><path d="M7 17 17 7M7 7h10v10" /></>,
    pulse: <><path d="M3 12h4l3-8 4 16 3-8h4" /></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>,
  }

  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  )
}

function App() {
  const [activePage, setActivePage] = useState<Page>('chat')
  const [connection, dispatchConnection] = useReducer(connectionReducer, 'checking')

  const checkBackend = useCallback(async () => {
    try {
      await fetchHealth()
      dispatchConnection({ type: 'resolved', connected: true })
    } catch {
      dispatchConnection({ type: 'resolved', connected: false })
    }
  }, [])

  const retryBackend = useCallback(() => {
    dispatchConnection({ type: 'checking' })
    void checkBackend()
  }, [checkBackend])

  useEffect(() => {
    void checkBackend()
    const timer = window.setInterval(() => void checkBackend(), 30_000)
    return () => window.clearInterval(timer)
  }, [checkBackend])

  const healthLabel = {
    checking: strings.health.checking,
    connected: strings.health.connected,
    disconnected: strings.health.disconnected,
  }[connection]

  const pageContent = {
    chat: {
      eyebrow: strings.chat.eyebrow,
      title: strings.chat.title,
      description: strings.chat.description,
    },
    knowledge: {
      eyebrow: strings.knowledge.eyebrow,
      title: strings.knowledge.title,
      description: strings.knowledge.description,
    },
    settings: {
      eyebrow: strings.settings.eyebrow,
      title: strings.settings.title,
      description: strings.settings.description,
    },
  }[activePage]

  return (
    <div className="app-shell" dir="rtl">
      <aside className="sidebar">
        <a className="brand" href="#main" aria-label={strings.brandAriaLabel}>
          <span className="brand-mark"><Icon name="sparkle" size={22} /></span>
          <span className="brand-copy">
            <strong>{strings.product}</strong>
            <small>{strings.productDescription}</small>
          </span>
        </a>

        <div className="sidebar-label">{strings.workspace}</div>
        <nav className="primary-nav" aria-label={strings.navigationLabel}>
          {navigation.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item${activePage === item.id ? ' is-active' : ''}`}
              aria-current={activePage === item.id ? 'page' : undefined}
              onClick={() => setActivePage(item.id)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.id === 'chat' && <span className="nav-indicator" aria-hidden="true" />}
            </button>
          ))}
        </nav>

        <div className="sidebar-spacer" />
        <div className="sidebar-health">
          <span className={`health-dot ${connection}`} aria-hidden="true" />
          <div className="health-copy">
            <strong>{healthLabel}</strong>
            <small>{strings.health.backend}</small>
          </div>
          {connection === 'disconnected' && (
            <button className="icon-button retry-button" type="button" onClick={retryBackend} aria-label={strings.health.retry} title={strings.health.retry}>
              <Icon name="pulse" size={17} />
            </button>
          )}
        </div>
        <div className="sidebar-footer"><span className="footer-mark" />{strings.footer}</div>
      </aside>

      <main className="main-area" id="main">
        <header className="topbar">
          <div className="breadcrumb"><span>{strings.product}</span><span className="breadcrumb-divider">/</span><span>{pageContent.eyebrow}</span></div>
          <div className={`connection-pill ${connection}`} role="status" aria-live="polite">
            <span className="health-dot" aria-hidden="true" />
            <span>{healthLabel}</span>
            {connection === 'disconnected' && (
              <button className="text-button" type="button" onClick={retryBackend}>{strings.health.retry}</button>
            )}
          </div>
        </header>

        <div className="content-wrap">
          <section className="page-heading" aria-labelledby="page-title">
            <div>
              <div className="eyebrow"><span className="eyebrow-line" />{pageContent.eyebrow}</div>
              <h1 id="page-title">{pageContent.title}</h1>
              <p>{pageContent.description}</p>
            </div>
            <div className="heading-decoration" aria-hidden="true"><Icon name="sparkle" size={28} /></div>
          </section>

          {activePage === 'chat' && (
            <section className="workspace-card chat-card" aria-label={strings.chat.title}>
              <div className="card-toolbar">
                <span className="toolbar-dot" /><span className="toolbar-dot" /><span className="toolbar-dot" />
                <span className="toolbar-label">{strings.chat.title}</span>
                <span className="toolbar-status"><Icon name="pulse" size={15} />{strings.health.storageReady}</span>
              </div>
              <div className="empty-state chat-empty">
                <div className="empty-illustration chat-illustration">
                  <span className="illustration-orbit orbit-one" />
                  <span className="illustration-orbit orbit-two" />
                  <span className="illustration-center"><Icon name="chat" size={26} /></span>
                  <span className="illustration-sparkle"><Icon name="sparkle" size={16} /></span>
                </div>
                <span className="empty-kicker">{strings.startReady}</span>
                <h2>{strings.chat.emptyTitle}</h2>
                <p>{strings.chat.emptyDescription}</p>
              </div>
              <div className="composer-wrap">
                <label className="sr-only" htmlFor="question-input">{strings.chat.composerLabel}</label>
                <div className="composer-input">
                  <input id="question-input" type="text" disabled placeholder={strings.chat.composerPlaceholder} />
                  <button type="button" disabled aria-label={strings.chat.send} className="send-button"><Icon name="arrow" size={19} /></button>
                </div>
                <div className="composer-note"><span className="note-dot" />{strings.chat.comingSoon}</div>
              </div>
            </section>
          )}

          {activePage === 'knowledge' && (
            <section className="workspace-card secondary-card">
              <div className="card-toolbar">
                <span className="toolbar-dot" /><span className="toolbar-dot" /><span className="toolbar-dot" />
                <span className="toolbar-label">{strings.knowledge.title}</span>
              </div>
              <div className="empty-state secondary-empty">
                <div className="empty-illustration library-illustration"><Icon name="library" size={27} /></div>
                <span className="empty-kicker">{strings.knowledgeLibrary}</span>
                <h2>{strings.knowledge.emptyTitle}</h2>
                <p>{strings.knowledge.emptyDescription}</p>
                <button className="primary-button" disabled type="button"><Icon name="sparkle" size={17} />{strings.knowledge.action}</button>
                <small className="disabled-note">{strings.knowledge.comingSoon}</small>
              </div>
            </section>
          )}

          {activePage === 'settings' && (
            <section className="settings-grid">
              <article className="setting-card">
                <div className="setting-icon"><Icon name="pulse" /></div>
                <div><span className="setting-label">{strings.settings.service}</span><h2>{strings.settings.serviceValue}</h2><p>{healthLabel}</p></div>
                <span className={`health-dot ${connection}`} aria-hidden="true" />
              </article>
              <article className="setting-card">
                <div className="setting-icon"><Icon name="database" /></div>
                <div><span className="setting-label">{strings.settings.storage}</span><h2>{strings.settings.storageValue}</h2><p>{strings.health.storageReady}</p></div>
                <span className="health-dot connected" aria-hidden="true" />
              </article>
              <div className="settings-note"><Icon name="sparkle" size={18} /><span>{strings.settings.note}</span></div>
            </section>
          )}

          <footer className="page-footer"><span>SUPPORTRECALL</span><span className="footer-separator" /><span>{strings.footer}</span></footer>
        </div>
      </main>
    </div>
  )
}

export default App

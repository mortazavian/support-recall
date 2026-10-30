import { useCallback, useEffect, useRef, useState } from 'react'
import type { DragEvent, ChangeEvent } from 'react'
import {
  ApiRequestError,
  deleteSource,
  fetchSourceDetail,
  fetchSources,
  importSource,
  previewSource,
  retrySource,
} from './api'
import type {
  CsvColumnMapping,
  ImportedConversation,
  SourceDetail,
  SourcePreview,
  SourceSummary,
} from './api'
import { strings } from './strings'

type MappingField = keyof CsvColumnMapping
type StatusKey = 'pending' | 'processing' | 'ready' | 'failed'

const statusLabels: Record<StatusKey, string> = {
  pending: strings.knowledge.statusPending,
  processing: strings.knowledge.statusProcessing,
  ready: strings.knowledge.statusReady,
  failed: strings.knowledge.statusFailed,
}

function KnowledgeView() {
  const [sources, setSources] = useState<SourceSummary[]>([])
  const [loadingSources, setLoadingSources] = useState(true)
  const [file, setFile] = useState<File | null>(null)
  const [columns, setColumns] = useState<string[]>([])
  const [mapping, setMapping] = useState<CsvColumnMapping>({ question: '', answer: '' })
  const [preview, setPreview] = useState<SourcePreview | null>(null)
  const [busy, setBusy] = useState<'preview' | 'import' | null>(null)
  const [busySourceId, setBusySourceId] = useState<string | null>(null)
  const [details, setDetails] = useState<SourceDetail | null>(null)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [activeDetailId, setActiveDetailId] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  const loadSources = useCallback(async () => {
    try {
      setSources(await fetchSources())
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setLoadingSources(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    void fetchSources()
      .then((result) => { if (active) setSources(result) })
      .catch((requestError: unknown) => { if (active) setError(errorMessage(requestError)) })
      .finally(() => { if (active) setLoadingSources(false) })
    return () => { active = false }
  }, [])

  const chooseFile = useCallback(async (nextFile: File | undefined) => {
    setError('')
    setNotice('')
    setPreview(null)
    setColumns([])
    setMapping({ question: '', answer: '' })
    setDetails(null)
    setActiveDetailId(null)
    if (!nextFile) {
      setFile(null)
      return
    }

    setFile(nextFile)
    setBusy('preview')
    try {
      const result = await previewSource(nextFile)
      setPreview(result)
      setColumns(result.columns)
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setBusy(null)
    }
  }, [])

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    void chooseFile(selected)
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    void chooseFile(event.dataTransfer.files[0])
  }

  function updateMapping(field: MappingField, value: string) {
    setMapping((current) => ({
      ...current,
      [field]: field === 'question' || field === 'answer' ? value : value || null,
    }))
  }

  async function createPreview() {
    if (!file) {
      setError(strings.knowledge.fileRequired)
      return
    }
    if (!mapping.question || !mapping.answer) {
      setError(strings.knowledge.mappingRequired)
      return
    }
    setError('')
    setNotice('')
    setBusy('preview')
    try {
      const result = await previewSource(file, cleanMapping(mapping))
      setPreview(result)
    } catch (requestError) {
      setPreview(null)
      setError(errorMessage(requestError))
    } finally {
      setBusy(null)
    }
  }

  async function confirmImport() {
    if (!file || !preview || preview.needs_mapping || preview.record_count === null) {
      setError(strings.knowledge.noPreview)
      return
    }
    setError('')
    setNotice('')
    setBusy('import')
    try {
      const result = await importSource(
        file,
        preview.format === 'csv' ? cleanMapping(mapping) : undefined,
      )
      setNotice(result.duplicate ? strings.knowledge.duplicateNotice : strings.knowledge.importSuccess)
      setFile(null)
      setPreview(null)
      setColumns([])
      setMapping({ question: '', answer: '' })
      await loadSources()
    } catch (requestError) {
      setError(errorMessage(requestError))
      await loadSources()
    } finally {
      setBusy(null)
    }
  }

  async function toggleDetails(sourceId: string) {
    setError('')
    if (activeDetailId === sourceId) {
      setActiveDetailId(null)
      setDetails(null)
      return
    }
    setActiveDetailId(sourceId)
    setDetailsLoading(true)
    try {
      setDetails(await fetchSourceDetail(sourceId))
    } catch (requestError) {
      setDetails(null)
      setError(errorMessage(requestError))
    } finally {
      setDetailsLoading(false)
    }
  }

  async function retryImport(sourceId: string) {
    setError('')
    setNotice('')
    setBusySourceId(sourceId)
    try {
      await retrySource(sourceId)
      setNotice(strings.knowledge.retrySuccess)
      await loadSources()
      if (activeDetailId === sourceId) setDetails(await fetchSourceDetail(sourceId))
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setBusySourceId(null)
    }
  }

  async function removeSource(source: SourceSummary) {
    if (!window.confirm(strings.knowledge.confirmDelete)) return
    setError('')
    setNotice('')
    setBusySourceId(source.id)
    try {
      await deleteSource(source.id)
      setSources((current) => current.filter((item) => item.id !== source.id))
      if (activeDetailId === source.id) {
        setActiveDetailId(null)
        setDetails(null)
      }
      setNotice(strings.knowledge.deleteSuccess)
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setBusySourceId(null)
    }
  }

  const canImport = Boolean(
    file && preview && !preview.needs_mapping && preview.record_count && preview.record_count > 0,
  )

  return (
    <div className="knowledge-workflow">
      <section className="upload-panel" aria-labelledby="upload-title">
        <div className="upload-panel-heading">
          <div>
            <h2 id="upload-title">{strings.knowledge.chooseFile}</h2>
            <p>{strings.knowledge.supportedFiles}</p>
          </div>
          <span className="upload-panel-icon" aria-hidden="true">＋</span>
        </div>

        <div
          className={`file-drop${dragging ? ' is-dragging' : ''}`}
          onDragEnter={(event) => { event.preventDefault(); setDragging(true) }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false)
          }}
          onDrop={onDrop}
        >
          <input
            ref={fileInput}
            className="sr-only"
            id="support-file"
            type="file"
            accept=".csv,.json,.txt"
            onChange={onFileChange}
            aria-label={strings.knowledge.fileInputLabel}
          />
          <span className="file-drop-icon" aria-hidden="true">↥</span>
          <p>{strings.knowledge.dropPrompt}</p>
          <button type="button" className="secondary-action" onClick={() => fileInput.current?.click()}>
            {strings.knowledge.chooseFile}
          </button>
          {file && <span className="selected-file" dir="auto">{file.name}</span>}
        </div>

        <div className="sample-downloads" aria-labelledby="samples-heading">
          <h3 id="samples-heading">{strings.knowledge.samplesTitle}</h3>
          <a href="/samples/نمونه-پشتیبانی.csv" download="نمونه-پشتیبانی.csv">
            {strings.knowledge.sampleCsv}
          </a>
          <a href="/samples/نمونه-پشتیبانی.json" download="نمونه-پشتیبانی.json">
            {strings.knowledge.sampleJson}
          </a>
          <a href="/samples/نمونه-پشتیبانی.txt" download="نمونه-پشتیبانی.txt">
            {strings.knowledge.sampleText}
          </a>
        </div>
      </section>

      {busy === 'preview' && (
        <p className="workflow-status" role="status">{strings.knowledge.loadingPreview}</p>
      )}
      {error && <p className="workflow-message is-error" role="alert">{error}</p>}
      {notice && <p className="workflow-message is-success" role="status">{notice}</p>}

      {preview?.needs_mapping && file && (
        <section className="mapping-panel" aria-labelledby="mapping-title">
          <div>
            <h2 id="mapping-title">{strings.knowledge.mappingTitle}</h2>
            <p>{strings.knowledge.mappingDescription}</p>
          </div>
          <div className="mapping-grid">
            <ColumnSelect
              label={strings.knowledge.questionColumn}
              value={mapping.question}
              columns={columns}
              required
              onChange={(value) => updateMapping('question', value)}
            />
            <ColumnSelect
              label={strings.knowledge.answerColumn}
              value={mapping.answer}
              columns={columns}
              required
              onChange={(value) => updateMapping('answer', value)}
            />
            <ColumnSelect
              label={strings.knowledge.conversationIdColumn}
              value={mapping.conversation_id ?? ''}
              columns={columns}
              onChange={(value) => updateMapping('conversation_id', value)}
            />
            <ColumnSelect
              label={strings.knowledge.dateColumn}
              value={mapping.date ?? ''}
              columns={columns}
              onChange={(value) => updateMapping('date', value)}
            />
            <ColumnSelect
              label={strings.knowledge.productColumn}
              value={mapping.product ?? ''}
              columns={columns}
              onChange={(value) => updateMapping('product', value)}
            />
            <ColumnSelect
              label={strings.knowledge.categoryColumn}
              value={mapping.category ?? ''}
              columns={columns}
              onChange={(value) => updateMapping('category', value)}
            />
          </div>
          <button
            className="primary-button"
            type="button"
            disabled={busy !== null || !mapping.question || !mapping.answer}
            onClick={() => void createPreview()}
          >
            {strings.knowledge.previewAction}
          </button>
        </section>
      )}

      {preview && !preview.needs_mapping && (
        <section className="preview-panel" aria-labelledby="preview-title">
          <div className="preview-panel-heading">
            <div>
              <span className="panel-eyebrow">{strings.knowledge.validationTitle}</span>
              <h2 id="preview-title">{strings.knowledge.previewTitle}</h2>
            </div>
            <span className="record-total" role="status">
              {formatCount(strings.knowledge.previewCount, preview.record_count ?? 0)}
            </span>
          </div>
          <ConversationList records={preview.records} />
          {(preview.record_count ?? 0) > preview.records.length && (
            <p className="preview-footnote">{strings.knowledge.previewTruncated}</p>
          )}
          <button
            className="primary-button"
            type="button"
            disabled={!canImport || busy !== null}
            onClick={() => void confirmImport()}
          >
            {busy === 'import' ? strings.knowledge.loadingImport : strings.knowledge.importAction}
          </button>
        </section>
      )}

      <section className="source-library" aria-labelledby="source-list-title">
        <div className="source-list-heading">
          <div>
            <span className="panel-eyebrow">{strings.knowledge.libraryEyebrow}</span>
            <h2 id="source-list-title">{strings.knowledge.sourceListTitle}</h2>
          </div>
          {!loadingSources && (
            <span className="record-total">{formatCount(strings.knowledge.sourceCount, sources.length)}</span>
          )}
        </div>
        {loadingSources ? (
          <p className="workflow-status" role="status">{strings.knowledge.loadingSources}</p>
        ) : sources.length === 0 ? (
          <div className="library-empty">
            <span className="empty-library-icon" aria-hidden="true">◇</span>
            <h3>{strings.knowledge.emptyTitle}</h3>
            <p>{strings.knowledge.emptyDescription}</p>
          </div>
        ) : (
          <div className="source-list">
            {sources.map((source) => (
              <article className="source-row" key={source.id}>
                <div className="source-file-mark" aria-hidden="true">{formatMark(source.format)}</div>
                <div className="source-main">
                  <h3 dir="auto">{source.filename}</h3>
                  <div className="source-meta">
                    <span>{formatCount(strings.knowledge.recordCount, source.record_count)}</span>
                    <span className="footer-separator" />
                    <span>{formatDate(source.created_at)}</span>
                  </div>
                  {source.error_message && <p className="source-error">{source.error_message}</p>}
                  {activeDetailId === source.id && (
                    <div className="source-details">
                      {detailsLoading ? (
                        <p className="workflow-status" role="status">{strings.knowledge.loadingDetails}</p>
                      ) : details?.source.id === source.id ? (
                        <>
                          <dl className="source-facts">
                            <div><dt>{strings.knowledge.filename}</dt><dd dir="auto">{details.source.filename}</dd></div>
                            <div><dt>{strings.knowledge.format}</dt><dd>{formatLabel(details.source.format)}</dd></div>
                            <div><dt>{strings.knowledge.importedAt}</dt><dd>{formatDate(details.source.created_at)}</dd></div>
                          </dl>
                          <h4>{strings.knowledge.detailsRecords}</h4>
                          <ConversationList records={details.records} />
                        </>
                      ) : null}
                    </div>
                  )}
                </div>
                <div className="source-actions">
                  <span className={`source-status is-${source.status}`} role="status">
                    {statusLabels[source.status]}
                  </span>
                  <button
                    className="quiet-action"
                    type="button"
                    aria-expanded={activeDetailId === source.id}
                    onClick={() => void toggleDetails(source.id)}
                  >
                    {activeDetailId === source.id
                      ? strings.knowledge.hideDetails
                      : strings.knowledge.showDetails}
                  </button>
                  {source.retryable && (
                    <button
                      className="quiet-action"
                      type="button"
                      disabled={busySourceId !== null}
                      onClick={() => void retryImport(source.id)}
                    >
                      {busySourceId === source.id ? strings.knowledge.loadingImport : strings.knowledge.retry}
                    </button>
                  )}
                  <button
                    className="quiet-action is-danger"
                    type="button"
                    disabled={busySourceId !== null}
                    onClick={() => void removeSource(source)}
                  >
                    {strings.knowledge.delete}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function ColumnSelect({
  label,
  value,
  columns,
  required = false,
  onChange,
}: {
  label: string
  value: string
  columns: string[]
  required?: boolean
  onChange: (value: string) => void
}) {
  return (
    <label className="mapping-field">
      <span>{label}{required ? ' *' : ''}</span>
      <select aria-label={label} required={required} value={value} onChange={(event) => onChange(event.target.value)}>
        {!required && <option value="">{strings.knowledge.noColumn}</option>}
        {columns.map((column) => <option key={column} value={column}>{column}</option>)}
      </select>
    </label>
  )
}

function ConversationList({ records }: { records: ImportedConversation[] }) {
  if (records.length === 0) return <p className="library-empty-copy">{strings.knowledge.noRecords}</p>
  return (
    <div className="conversation-preview-list">
      {records.map((record, index) => (
        <article className="conversation-preview" key={`${record.conversation_id ?? 'row'}-${index}`}>
          <div className="conversation-meta">
            {record.conversation_id && <span dir="auto">{record.conversation_id}</span>}
            {record.date && <span>{strings.knowledge.date}: {record.date}</span>}
            {record.product && <span>{record.product}</span>}
            {record.category && <span>{record.category}</span>}
          </div>
          <ol className="conversation-messages">
            {record.messages.map((message, messageIndex) => (
              <li className={`conversation-message is-${message.role}`} key={messageIndex}>
                <span>{message.role === 'customer' ? strings.knowledge.customer : strings.knowledge.support}</span>
                <p dir="auto">{message.content}</p>
              </li>
            ))}
          </ol>
        </article>
      ))}
    </div>
  )
}

function cleanMapping(mapping: CsvColumnMapping): CsvColumnMapping {
  return {
    question: mapping.question,
    answer: mapping.answer,
    conversation_id: mapping.conversation_id || null,
    date: mapping.date || null,
    product: mapping.product || null,
    category: mapping.category || null,
  }
}

function errorMessage(error: unknown): string {
  return error instanceof ApiRequestError ? error.message : strings.knowledge.requestFailed
}

function formatCount(template: string, count: number): string {
  return template.replace('{count}', count.toLocaleString('fa-IR'))
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString('fa-IR')
}

function formatLabel(format: SourceSummary['format']): string {
  if (format === 'csv') return 'CSV'
  return format === 'json' ? 'JSON' : 'متن ساده'
}

function formatMark(format: SourceSummary['format']): string {
  if (format === 'csv') return 'CSV'
  return format === 'json' ? 'JS' : 'TXT'
}

export default KnowledgeView

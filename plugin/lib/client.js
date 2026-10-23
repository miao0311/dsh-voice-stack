/**
 * dsh-voice-status — browser half.
 *
 * A small indicator in the sidebar footer: 🎙 plus three dots, one per component
 * of the voice stack (read-aloud, thought extractor, guard). Green means its
 * heartbeat is fresh; red means it has gone quiet.
 *
 * Clicking opens a card with each component's heartbeat age and the tail of its
 * log, so "why is there no sound" can be answered without opening a terminal.
 */
window.__ModuleLoader__.load({
  id: 'dsh-voice-status',
  factory: (require) => {
    var module = { exports: {} }
    var exports = module.exports
    Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' })

    const react = require('react')
    const jsxRuntime = require('react/jsx-runtime')
    const { useState, useEffect, useRef } = react
    const { jsx, jsxs } = jsxRuntime

    const ROUTE = '/api/voice-status'
    const POLL_MS = 5000

    const COMPONENTS = [
      { key: 'watch', label: '朗读守候', file: 'watch.py' },
      { key: 'think', label: '思考提取', file: 'watch_think.py' },
      { key: 'guard', label: '守护进程', file: 'guard.ps1' },
    ]

    function StatusButton() {
      const [state, setState] = useState(null)
      const [open, setOpen] = useState(false)
      const btnRef = useRef(null)
      // 实测的侧栏宽度；0 表示还没量到，用兜底值
      const [panelWidth, setPanelWidth] = useState(0)

      useEffect(() => {
        let alive = true
        const tick = () => {
          fetch(`${ROUTE}/state`, { headers: { accept: 'application/json' } })
            .then((r) => r.json())
            .then((d) => {
              if (alive && d && d.ok) setState(d)
            })
            .catch(() => {})
        }
        tick()
        const timer = window.setInterval(tick, POLL_MS)
        return () => {
          alive = false
          window.clearInterval(timer)
        }
      }, [])

      // 打开面板时量一次侧栏宽度；窗口/侧栏尺寸变了跟着更新
      useEffect(() => {
        if (!open) return undefined
        const btn = btnRef.current
        if (!btn) return undefined

        const host = btn.closest('aside, nav') || btn.parentElement
        if (!host) return undefined

        const measure = () => {
          const rect = host.getBoundingClientRect()
          if (rect.width > 80) {
            // 留 12px 给左右边距，上限 260 免得在大屏上摊太开
            setPanelWidth(Math.max(150, Math.min(rect.width - 12, 260)))
          }
        }
        measure()

        let observer
        if (typeof ResizeObserver !== 'undefined') {
          observer = new ResizeObserver(measure)
          observer.observe(host)
        } else {
          window.addEventListener('resize', measure)
        }
        return () => {
          if (observer) observer.disconnect()
          else window.removeEventListener('resize', measure)
        }
      }, [open])

      const staleAfter = (state && state.staleAfter) || 90
      const isAlive = (age) => typeof age === 'number' && age >= 0 && age < staleAfter

      const ageText = (age) => {
        if (typeof age !== 'number') return '—'
        if (age < 0) return '未运行'
        if (age < 60) return `${age} 秒前`
        if (age < 3600) return `${Math.round(age / 60)} 分钟前`
        return `${Math.round(age / 3600)} 小时前`
      }

      const aliveCount = state
        ? COMPONENTS.filter((c) => isAlive(state[c.key])).length
        : 0

      const dot = (age) =>
        jsx('span', {
          style: {
            width: 5,
            height: 5,
            borderRadius: 3,
            display: 'inline-block',
            background: isAlive(age)
              ? 'var(--dsw-alias-state-success-primary)'
              : 'var(--dsw-alias-state-error-primary)',
            opacity: isAlive(age) ? 1 : 0.7,
          },
        })

      const button = jsxs('button', {
        ref: btnRef,
        type: 'button',
        title: state ? `语音系统 ${aliveCount}/3 在运行` : '语音系统状态',
        onClick: () => setOpen((v) => !v),
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          padding: '2px 6px',
          border: 'none',
          borderRadius: 6,
          background: open ? 'var(--dsw-alias-bg-layer-2)' : 'transparent',
          color: 'var(--dsw-alias-label-secondary)',
          cursor: 'pointer',
          fontSize: 11,
          lineHeight: 1,
          fontFamily: 'inherit',
        },
        children: [
          jsx('span', { style: { fontSize: 12 }, children: '🎙' }),
          ...(state
            ? [dot(state.watch), dot(state.think), dot(state.guard)]
            : []),
        ],
      })

      const row = (c) => {
        const age = state ? state[c.key] : null
        return jsxs('div', {
          style: {
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 10,
            padding: '3px 0',
            fontSize: 11,
          },
          children: [
            jsxs('div', {
              style: { display: 'flex', alignItems: 'center', gap: 6 },
              children: [
                dot(age),
                jsx('span', {
                  style: { color: 'var(--dsw-alias-label-primary)' },
                  children: c.label,
                }),
              ],
            }),
            jsx('span', {
              style: {
                color: isAlive(age)
                  ? 'var(--dsw-alias-label-secondary)'
                  : 'var(--dsw-alias-state-error-primary)',
                whiteSpace: 'nowrap',
              },
              children: ageText(age),
            }),
          ],
        })
      }


      const panel = open
        ? jsxs('div', {
            style: {
              position: 'absolute',
              bottom: 'calc(100% + 8px)',
              right: 0,
              width: panelWidth || 192,
              padding: '7px 9px',
              background: 'var(--dsw-alias-bg-overlay)',
              border: '1px solid var(--dsw-alias-border-l1)',
              borderRadius: 10,
              boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
              zIndex: 60,
              fontFamily: 'var(--dsw-font-family)',
            },
            children: [
              jsxs('div', {
                style: {
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 4,
                },
                children: [
                  jsx('span', {
                    style: {
                      fontSize: 12,
                      fontWeight: 600,
                      color: 'var(--dsw-alias-label-primary)',
                    },
                    children: '语音系统',
                  }),
                  jsx('span', {
                    style: {
                      fontSize: 10,
                      color:
                        aliveCount === COMPONENTS.length
                          ? 'var(--dsw-alias-state-success-primary)'
                          : 'var(--dsw-alias-state-error-primary)',
                    },
                    children: `${aliveCount}/${COMPONENTS.length} 在运行`,
                  }),
                ],
              }),
              ...COMPONENTS.map(row),
              jsx('div', {
                style: {
                  marginTop: 6,
                  paddingTop: 5,
                  borderTop: '1px solid var(--dsw-alias-border-l1)',
                  fontSize: 10,
                  color: 'var(--dsw-alias-label-secondary)',
                  opacity: 0.7,
                },
                children: `${staleAfter}s 无心跳算掉线 · 每 ${POLL_MS / 1000}s 刷新`,
              }),
            ],
          })
        : null

      return jsxs('div', {
        style: { position: 'relative', display: 'inline-flex' },
        children: [button, panel],
      })
    }

    const inject = ['slots']

    function apply(ctx) {
      ctx.slots.inject('sidebar.footer.action', () =>
        ctx.slots.register(
          {
            name: 'sidebar.footer.action',
            id: 'dsh-voice-status',
            order: 30,
            label: () => '语音',
          },
          StatusButton,
        ),
      )
    }

    exports.apply = apply
    exports.inject = inject
    return module.exports
  },
})

/**
 * dsh-voice-status — host half.
 *
 * Exposes one endpoint so the UI can show whether the voice stack is alive:
 *
 *   GET /api/voice-status -> {
 *     ok, watch, think, guard,    // 各自心跳距今多少秒；-1 表示文件不存在
 *     logs: { watch: [...], think: [...], guard: [...] }
 *   }
 *
 * Why heartbeats instead of process inspection: from Node, deciding whether a
 * given `pythonw.exe` is *our* watch.py means running tasklist/wmic and parsing
 * command lines — slow, and watch.py vs watch_think.py look identical by name.
 * Each component touches its own `.beat` file every few seconds; freshness of that
 * mtime answers "is it alive" in one stat call.
 */
import { readFile, stat } from 'node:fs/promises'
import { join } from 'node:path'

const name = 'dsh-voice-status'
const inject = ['webServer']

const ROUTE_PREFIX = '/api/voice-status'
// 语音系统的家目录。开源版不能写死盘符，规则跟 core/config.py 一致：
// 优先 DSH_VOICE_HOME，否则 <用户目录>/.dsh/voice-stack
const VOICE_HOME =
  process.env.DSH_VOICE_HOME ||
  join(
    process.env.USERPROFILE || process.env.HOME || '.',
    '.dsh',
    'voice-stack',
  )

/** A heartbeat older than this counts as dead. */
const STALE_SECONDS = 90

const JSON_HEADERS = {
  'content-type': 'application/json; charset=utf-8',
  'cache-control': 'no-store',
}

function sendJson(res, status, body) {
  res.writeHead(status, JSON_HEADERS)
  res.end(JSON.stringify(body))
}

/** Seconds since the heartbeat file was touched; -1 when missing. */
async function beatAge(file) {
  try {
    const st = await stat(join(VOICE_HOME, file))
    return Math.max(0, Math.round((Date.now() - st.mtimeMs) / 1000))
  } catch {
    return -1
  }
}

/** Last N non-empty lines of a log file (all of it if short). */
async function tail(file, count) {
  try {
    const raw = await readFile(join(VOICE_HOME, file), 'utf8')
    const lines = raw.split(/\r?\n/).filter((l) => l.trim())
    return lines.slice(-count)
  } catch {
    return []
  }
}

function apply(ctx) {
  ctx.effect(() =>
    ctx.webServer.register({
      kind: 'prefix',
      path: ROUTE_PREFIX,
      handler: async (req, res) => {
        try {
          const url = new URL(req.url ?? '/', 'http://x')
          const pathname = decodeURIComponent(url.pathname)

          if (pathname === `${ROUTE_PREFIX}/state`) {
            const [watch, think, guard] = await Promise.all([
              beatAge('watch.beat'),
              beatAge('think.beat'),
              beatAge('guard.beat'),
            ])
            const [watchLog, thinkLog, guardLog] = await Promise.all([
              tail('watch.log', 4),
              tail('think.log', 4),
              tail('guard.log', 4),
            ])
            sendJson(res, 200, {
              ok: true,
              staleAfter: STALE_SECONDS,
              watch,
              think,
              guard,
              logs: { watch: watchLog, think: thinkLog, guard: guardLog },
            })
            return
          }

          sendJson(res, 404, { ok: false, error: 'not-found' })
        } catch (error) {
          sendJson(res, 500, { ok: false, error: String(error?.message ?? error) })
        }
      },
    }),
  )
}

export { name, inject, apply }

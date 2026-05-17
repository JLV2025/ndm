import { useEffect, useRef } from 'react'

const MATRIX_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*()_+-=[]{}|;:\',.<>?/`吕京网络妮二宝娟'
const FONT_SIZE = 14
const FADE_ALPHA = 0.035

const HEAD_COLOR = '#FFFFFF'
const BRIGHT_COLOR = '#00FF41'
const DIM_COLOR = '#00cc33'

export default function MatrixRain() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number>(0)
  const dropsRef = useRef<number[]>([])
  const resizeRef = useRef<ResizeObserver | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let cols = 0
    let drops: number[] = []
    let running = true
    let frameCount = 0

    const resize = () => {
      const parent = canvas.parentElement
      if (!parent) return
      const w = parent.clientWidth
      const h = parent.clientHeight
      canvas.width = w
      canvas.height = h
      cols = Math.floor(w / FONT_SIZE)
      drops = Array.from({ length: cols }, () => Math.random() * -100)
      dropsRef.current = drops
    }

    resize()
    if (canvas.parentElement) {
      resizeRef.current = new ResizeObserver(resize)
      resizeRef.current.observe(canvas.parentElement)
    }

    const draw = () => {
      if (!running || !ctx || !canvas) return

      frameCount++

      ctx.fillStyle = `rgba(2, 6, 23, ${FADE_ALPHA})`
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      ctx.font = `${FONT_SIZE}px "JetBrains Mono", monospace`

      const advance = frameCount % 6 === 0

      for (let i = 0; i < drops.length; i++) {
        const x = i * FONT_SIZE
        const y = drops[i] * FONT_SIZE

        const char = MATRIX_CHARS[Math.floor(Math.random() * MATRIX_CHARS.length)]

        if (drops[i] > 0 && drops[i] < 8) {
          ctx.fillStyle = BRIGHT_COLOR
        } else {
          ctx.fillStyle = DIM_COLOR
        }
        ctx.fillText(char, x, y)

        if (drops[i] > 0 && drops[i] < 3) {
          ctx.fillStyle = HEAD_COLOR
          ctx.fillText(char, x, y)
        }

        if (advance) {
          drops[i]++
        }

        if (y > canvas.height && Math.random() > 0.975) {
          drops[i] = 0
        }
      }

      rafRef.current = requestAnimationFrame(draw)
    }

    rafRef.current = requestAnimationFrame(draw)

    return () => {
      running = false
      cancelAnimationFrame(rafRef.current)
      resizeRef.current?.disconnect()
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 0,
        pointerEvents: 'none',
        opacity: 0.7,
      }}
    />
  )
}

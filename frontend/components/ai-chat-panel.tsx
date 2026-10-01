"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Bot, Loader2, MessageCircle, Send, Sparkles, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { aura } from "@/lib/aura-styles"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { ChatHistoryItem } from "@/app/api/chat/route"

interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
}

const WELCOME: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "嗨！我是你的充電樁小幫手 ⚡ 可以問我快充跟慢充的差別、特斯拉適用哪種樁、或怎麼規劃充電路線喔！",
}

export function AiChatPanel({ stacked = false }: { stacked?: boolean }) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isOpen && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, isOpen, isLoading])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || isLoading) return

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
    }

    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setIsLoading(true)
    setError(null)

    const history: ChatHistoryItem[] = messages
      .filter((m) => m.id !== "welcome")
      .map((m) => ({ role: m.role, content: m.content }))

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userMessage: text, history }),
      })

      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? "請求失敗")

      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.reply,
        },
      ])
    } catch (e) {
      const msg = e instanceof Error ? e.message : "無法取得 AI 回覆"
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }, [input, isLoading, messages])

  return (
    <>
      {!isOpen && (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className={cn(
            "w-14 h-14 rounded-2xl flex items-center justify-center shrink-0",
            !stacked && "absolute bottom-24 right-4 z-40",
            "bg-gradient-to-br from-violet-600 to-indigo-600 text-white",
            "shadow-xl shadow-violet-600/40 ring-2 ring-white/50",
            "hover:scale-105 active:scale-95 transition-all duration-300"
          )}
          aria-label="開啟 AI 助理"
          title="AI 充電樁助理"
        >
          <Sparkles className="w-7 h-7" />
        </button>
      )}

      {isOpen && (
        <div
          className={cn(
            stacked
              ? "absolute bottom-0 right-0 z-[60] w-[min(100vw-2rem,380px)] h-[min(70vh,520px)]"
              : "absolute bottom-4 right-4 z-50 w-[min(100vw-2rem,380px)] h-[min(70vh,520px)]",
            "flex flex-col rounded-2xl overflow-hidden shadow-2xl",
            aura.glassCard,
            "backdrop-blur-xl border-white/40"
          )}
        >
          <div className="flex items-center gap-3 px-4 py-3 border-b border-white/30 dark:border-white/10 bg-gradient-to-r from-violet-600/10 to-emerald-600/10">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-bold text-sm text-foreground">AI 充電樁助理</h3>
              <p className="text-[11px] text-muted-foreground">Gemini · 繁體中文</p>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className={cn("w-9 h-9 rounded-xl flex items-center justify-center", aura.btnGhost)}
              aria-label="關閉"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  "flex gap-2",
                  msg.role === "user" ? "justify-end" : "justify-start"
                )}
              >
                {msg.role === "assistant" && (
                  <div className="w-7 h-7 rounded-lg bg-violet-600/15 flex items-center justify-center shrink-0 mt-0.5">
                    <MessageCircle className="w-3.5 h-3.5 text-violet-600" />
                  </div>
                )}
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
                    msg.role === "user"
                      ? "bg-emerald-600 text-white rounded-br-md"
                      : "bg-white/80 dark:bg-zinc-800/80 text-foreground border border-white/40 dark:border-white/10 rounded-bl-md shadow-sm"
                  )}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex items-center gap-2 text-muted-foreground text-sm pl-9">
                <Loader2 className="w-4 h-4 animate-spin text-violet-600" />
                思考中…
              </div>
            )}
            {error && (
              <p className="text-xs text-destructive bg-destructive/10 rounded-lg px-3 py-2">
                {error}
              </p>
            )}
          </div>

          <form
            className="p-3 border-t border-white/30 dark:border-white/10 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              sendMessage()
            }}
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="問我充電相關問題…"
              disabled={isLoading}
              className={cn(aura.glassInset, "flex-1 h-11 rounded-xl text-sm")}
            />
            <Button
              type="submit"
              disabled={isLoading || !input.trim()}
              className={cn("h-11 w-11 rounded-xl shrink-0 p-0", aura.btnPrimary)}
            >
              <Send className="w-4 h-4" />
            </Button>
          </form>
        </div>
      )}
    </>
  )
}

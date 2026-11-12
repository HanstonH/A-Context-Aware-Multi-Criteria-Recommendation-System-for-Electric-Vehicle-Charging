import { GoogleGenerativeAI } from "@google/generative-ai"
import { NextResponse } from "next/server"

const SYSTEM_PROMPT =
  "你是一個活潑親切的台灣電動車充電樁專家 AI 助理，請用繁體中文回答，並根據使用者的需求給予建議。"

export interface ChatHistoryItem {
  role: "user" | "assistant"
  content: string
}

export async function POST(request: Request) {
  try {
    const apiKey = process.env.GEMINI_API_KEY
    if (!apiKey || apiKey === "YOUR_GEMINI_KEY") {
      return NextResponse.json(
        { error: "伺服器未設定 GEMINI_API_KEY，請在 .env.local 填入有效金鑰" },
        { status: 500 }
      )
    }

    const body = await request.json()
    const userMessage = typeof body.userMessage === "string" ? body.userMessage.trim() : ""
    const history: ChatHistoryItem[] = Array.isArray(body.history) ? body.history : []

    if (!userMessage) {
      return NextResponse.json({ error: "請提供 userMessage" }, { status: 400 })
    }

    const genAI = new GoogleGenerativeAI(apiKey)
    const model = genAI.getGenerativeModel({
      model: "gemini-2.5-flash",
      systemInstruction: SYSTEM_PROMPT,
    })

    const chat = model.startChat({
      history: history
        .filter((m) => m.content?.trim())
        .map((m) => ({
          role: m.role === "assistant" ? "model" : "user",
          parts: [{ text: m.content }],
        })),
    })

    const result = await chat.sendMessage(userMessage)
    const reply = result.response.text()

    return NextResponse.json({ reply })
  } catch (error) {
    console.error("[api/chat]", error)
    const message = error instanceof Error ? error.message : "AI 回覆失敗"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}

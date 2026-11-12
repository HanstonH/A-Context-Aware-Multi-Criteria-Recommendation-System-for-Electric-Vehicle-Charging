"use client"

import { useCallback, useState } from "react"
import {
  fetchRecommendations,
  type RecommendItem,
  type RecommendRequest,
} from "@/lib/api/recommend"

export function useRecommend() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [items, setItems] = useState<RecommendItem[]>([])

  const recommend = useCallback(async (payload: RecommendRequest) => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await fetchRecommendations(payload)
      setItems(result.items)
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : "取得 AI 推薦失敗"
      setError(message)
      setItems([])
      throw e instanceof Error ? e : new Error(message)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const clear = useCallback(() => {
    setItems([])
    setError(null)
  }, [])

  return {
    isLoading,
    error,
    items,
    recommend,
    clear,
  }
}

import React, { createContext, useContext, useState, useCallback } from 'react'
import zh from './zh'
import en from './en'

type Lang = 'zh' | 'en'
type TFunc = (key: string, fallback?: string) => string

const dictionaries: Record<Lang, Record<string, string>> = { zh, en }
const STORAGE_KEY = 'ndm-lang'

function detectLanguage(): Lang {
  // 1. 用户之前的选择
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'zh' || saved === 'en') return saved

  // 2. 浏览器语言
  const navLang = navigator.language || (navigator as any).userLanguage || ''
  if (navLang.toLowerCase().startsWith('zh')) return 'zh'

  // 3. 默认中文
  return 'zh'
}

interface I18nContextValue {
  lang: Lang
  t: TFunc
  setLang: (lang: Lang) => void
}

const I18nContext = createContext<I18nContextValue>({
  lang: 'zh',
  t: (key, fallback) => fallback ?? key,
  setLang: () => {},
})

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Lang>(detectLanguage)

  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    localStorage.setItem(STORAGE_KEY, l)
  }, [])

  const t: TFunc = useCallback(
    (key: string, fallback?: string) => {
      return dictionaries[lang][key] ?? fallback ?? key
    },
    [lang],
  )

  const value = { lang, t, setLang }

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  return useContext(I18nContext)
}

export type { Lang }

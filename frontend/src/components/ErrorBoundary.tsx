import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Box, Paper, Typography, Button } from '@mui/material'
import { ErrorOutline } from '@mui/icons-material'
import zhDict from '../i18n/zh'
import enDict from '../i18n/en'

const dictionaries = { zh: zhDict, en: enDict }

function getLang(): 'zh' | 'en' {
  const saved = localStorage.getItem('ndm-lang')
  if (saved === 'zh' || saved === 'en') return saved
  const nav = navigator.language || ''
  return nav.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      const lang = getLang()
      const t = (key: string) => dictionaries[lang][key] ?? key
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', p: 3 }}>
          <Paper sx={{ p: 4, maxWidth: 500, textAlign: 'center' }}>
            <ErrorOutline color="error" sx={{ fontSize: 64, mb: 2 }} />
            <Typography variant="h5" sx={{ fontWeight: 600, mb: 1 }}>
              {t('common.appError')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {this.state.error?.message || t('common.unknownError')}
            </Typography>
            <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mb: 3 }}>
              {t('common.errorHint')}
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
              <Button variant="outlined" onClick={this.handleReset}>
                {t('common.retry')}
              </Button>
              <Button variant="contained" onClick={() => window.location.reload()}>
                {t('common.refreshPage')}
              </Button>
            </Box>
          </Paper>
        </Box>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary

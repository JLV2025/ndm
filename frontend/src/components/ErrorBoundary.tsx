import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Box, Paper, Typography, Button } from '@mui/material'
import { ErrorOutline } from '@mui/icons-material'

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
    console.error('ErrorBoundary 捕获到错误:', error, info.componentStack)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', p: 3 }}>
          <Paper sx={{ p: 4, maxWidth: 500, textAlign: 'center' }}>
            <ErrorOutline color="error" sx={{ fontSize: 64, mb: 2 }} />
            <Typography variant="h5" sx={{ fontWeight: 600, mb: 1 }}>
              应用发生错误
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {this.state.error?.message || '未知错误'}
            </Typography>
            <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mb: 3 }}>
              请尝试刷新页面，或联系管理员
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
              <Button variant="outlined" onClick={this.handleReset}>
                重试
              </Button>
              <Button variant="contained" onClick={() => window.location.reload()}>
                刷新页面
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

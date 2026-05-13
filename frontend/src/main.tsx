import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import App from './App'

// 网络工程师风格 - 深色科技主题
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#2563eb',
      light: '#3b82f6',
      dark: '#1d4ed8',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#06b6d4',
      light: '#22d3ee',
      dark: '#0891b2',
      contrastText: '#ffffff',
    },
    success: {
      main: '#10b981',
      light: '#34d399',
      dark: '#059669',
      contrastText: '#ffffff',
    },
    warning: {
      main: '#f59e0b',
      light: '#fbbf24',
      dark: '#d97706',
      contrastText: '#000000',
    },
    error: {
      main: '#ef4444',
      light: '#f87171',
      dark: '#dc2626',
      contrastText: '#ffffff',
    },
    info: {
      main: '#06b6d4',
      light: '#22d3ee',
      dark: '#0891b2',
      contrastText: '#000000',
    },
    background: {
      default: '#0a0f1a',
      paper: '#0d121f',
    },
    text: {
      primary: '#e2e8f0',
      secondary: '#94a3b8',
      disabled: '#64748b',
    },
    divider: 'rgba(52, 211, 153, 0.1)',
  },
  typography: {
    fontFamily: '"Fira Code", "JetBrains Mono", "Roboto Mono", "Roboto", "Courier New", monospace',
    h1: { fontWeight: 700, letterSpacing: '-0.02em', color: '#ffffff' },
    h2: { fontWeight: 700, letterSpacing: '-0.015em', color: '#ffffff' },
    h3: { fontWeight: 600, letterSpacing: '-0.01em', color: '#ffffff' },
    h4: { fontWeight: 600, color: '#ffffff' },
    h5: { fontWeight: 600, color: '#ffffff' },
    h6: { fontWeight: 600, color: '#e2e8f0' },
    subtitle1: { fontWeight: 500, color: '#e2e8f0' },
    subtitle2: { fontWeight: 500, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.75rem' },
    body1: { fontWeight: 400, color: '#e2e8f0', fontSize: '0.875rem' },
    body2: { fontWeight: 500, color: '#94a3b8', fontSize: '0.875rem' },
    caption: { fontWeight: 500, color: '#64748b', fontSize: '0.75rem' },
    button: { fontWeight: 700, textTransform: 'none', letterSpacing: '0.025em' },
  },
  shape: {
    borderRadius: 12,
  },
  shadows: [
    'none',
    '0 1px 2px rgba(0, 0, 0, 0.3)',
    '0 2px 4px rgba(0, 0, 0, 0.3)',
    '0 4px 8px rgba(0, 0, 0, 0.3)',
    '0 8px 16px rgba(0, 0, 0, 0.3)',
    '0 12px 24px rgba(0, 0, 0, 0.3)',
    '0 16px 32px rgba(0, 0, 0, 0.3)',
    '0 20px 40px rgba(0, 0, 0, 0.3)',
    '0 24px 48px rgba(0, 0, 0, 0.3)',
    '0 28px 56px rgba(0, 0, 0, 0.3)',
    '0 32px 64px rgba(0, 0, 0, 0.3)',
    '0 36px 72px rgba(0, 0, 0, 0.3)',
    '0 0 0 1px rgba(37, 99, 235, 0.2), 0 16px 32px rgba(0, 0, 0, 0.3)',
    '0 8px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.3)',
    '0 0 40px rgba(37, 99, 235, 0.3), 0 16px 48px rgba(0, 0, 0, 0.4)',
    '0 0 60px rgba(37, 99, 235, 0.4), 0 24px 64px rgba(0, 0, 0, 0.4)',
    '0 0 80px rgba(6, 182, 212, 0.3), 0 32px 80px rgba(0, 0, 0, 0.4)',
    '0 0 100px rgba(52, 211, 153, 0.2), 0 40px 96px rgba(0, 0, 0, 0.4)',
    '0 0 120px rgba(37, 99, 235, 0.25), 0 48px 112px rgba(0, 0, 0, 0.4)',
    '0 0 140px rgba(6, 182, 212, 0.2), 0 56px 128px rgba(0, 0, 0, 0.4)',
    '0 0 160px rgba(52, 211, 153, 0.15), 0 64px 144px rgba(0, 0, 0, 0.4)',
    '0 0 180px rgba(37, 99, 235, 0.15), 0 72px 160px rgba(0, 0, 0, 0.4)',
    '0 0 200px rgba(6, 182, 212, 0.1), 0 80px 176px rgba(0, 0, 0, 0.4)',
    '0 0 220px rgba(52, 211, 153, 0.1), 0 88px 192px rgba(0, 0, 0, 0.4)',
    '0 0 240px rgba(37, 99, 235, 0.1), 0 96px 208px rgba(0, 0, 0, 0.4)',
  ],
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: '#111827',
          border: '1px solid rgba(52, 211, 153, 0.1)',
          boxShadow: '0 4px 16px rgba(0, 0, 0, 0.3)',
          transition: 'all 300ms ease',
          '&:hover': {
            borderColor: '#34d399',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(52, 211, 153, 0.2)',
            transform: 'translateY(-2px)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: '#0d121f',
          border: '1px solid rgba(52, 211, 153, 0.1)',
          boxShadow: '0 4px 16px rgba(0, 0, 0, 0.3)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          fontWeight: 700,
          textTransform: 'none',
          letterSpacing: '0.025em',
        },
        containedPrimary: {
          backgroundColor: '#2563eb',
          '&:hover': {
            backgroundColor: '#3b82f6',
            boxShadow: '0 0 20px rgba(37, 99, 235, 0.4)',
          },
        },
        containedSecondary: {
          backgroundColor: '#06b6d4',
          '&:hover': {
            backgroundColor: '#22d3ee',
            boxShadow: '0 0 20px rgba(6, 182, 212, 0.4)',
          },
        },
        outlined: {
          borderWidth: 1.5,
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            backgroundColor: '#0d121f',
            border: '1px solid rgba(148, 163, 184, 0.2)',
            borderRadius: 12,
            '&:hover': {
              border: '1px solid rgba(52, 211, 153, 0.4)',
            },
            '&.Mui-focused': {
              border: '1px solid #34d399',
              boxShadow: '0 0 0 3px rgba(52, 211, 153, 0.15)',
            },
            '& fieldset': {
              borderColor: 'rgba(148, 163, 184, 0.2)',
            },
            '&:hover fieldset': {
              borderColor: 'rgba(52, 211, 153, 0.4)',
            },
            '&.Mui-focused fieldset': {
              borderColor: '#34d399',
            },
          },
          '& .MuiInputLabel-root': {
            color: 'rgba(148, 163, 184, 0.5)',
            fontWeight: 500,
            '&.Mui-focused': {
              color: '#34d399',
            },
          },
          '& .MuiOutlinedInput-input': {
            padding: '16px 16px',
            color: '#e2e8f0',
          },
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        root: {
          backgroundColor: '#0d121f',
          border: '1px solid rgba(148, 163, 184, 0.2)',
          borderRadius: 12,
          '&:hover': {
            border: '1px solid rgba(52, 211, 153, 0.4)',
          },
          '&.Mui-focused': {
            border: '1px solid #34d399',
            boxShadow: '0 0 0 3px rgba(52, 211, 153, 0.15)',
          },
          '& .MuiOutlinedInput-notchedOutline': {
            border: 'none',
          },
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: {
          backgroundColor: '#0d121f',
          color: '#e2e8f0',
          '&:hover': {
            backgroundColor: 'rgba(52, 211, 153, 0.1)',
          },
          '&.Mui-selected': {
            backgroundColor: 'rgba(52, 211, 153, 0.15)',
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(52, 211, 153, 0.05)',
          backgroundColor: '#0d121f',
        },
        head: {
          fontWeight: 600,
          color: '#94a3b8',
          textTransform: 'uppercase',
          fontSize: '0.7rem',
          letterSpacing: '0.05em',
          backgroundColor: '#111827',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:nth-of-type(even)': {
            backgroundColor: '#0a0f1a',
          },
          '&:hover': {
            backgroundColor: 'rgba(52, 211, 153, 0.05)',
          },
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(52, 211, 153, 0.1)',
        },
        indicator: {
          backgroundColor: '#34d399',
          boxShadow: '0 0 12px rgba(52, 211, 153, 0.4)',
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          fontWeight: 500,
          color: '#94a3b8',
          '&.Mui-selected': {
            color: '#34d399',
            fontWeight: 600,
          },
          '&:hover': {
            color: '#34d399',
            backgroundColor: 'rgba(52, 211, 153, 0.05)',
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#0d121f',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.3)',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: '#0d121f',
          borderRight: '1px solid rgba(52, 211, 153, 0.1)',
        },
      },
    },
    MuiAvatar: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(52, 211, 153, 0.2)',
          color: '#34d399',
          border: '1px solid rgba(52, 211, 153, 0.3)',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
          height: 32,
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 12,
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: '#0d121f',
          border: '1px solid rgba(52, 211, 153, 0.1)',
          boxShadow: '0 24px 48px rgba(0, 0, 0, 0.4), 0 0 24px rgba(52, 211, 153, 0.1)',
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(52, 211, 153, 0.1)',
        },
      },
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <CssBaseline />
    <BrowserRouter>
      <ThemeProvider theme={theme}>
        <App />
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
)

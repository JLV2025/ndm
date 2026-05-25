import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import App from './App'
import { I18nProvider } from './i18n'

// 字体自托管（打包进 dist，无需外网）
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-sans/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/600.css'

// OLED Dark — 专业网络工具面板主题
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#22C55E',
      light: '#4ADE80',
      dark: '#16A34A',
      contrastText: '#020617',
    },
    secondary: {
      main: '#334155',
      light: '#475569',
      dark: '#1E293B',
      contrastText: '#F8FAFC',
    },
    success: {
      main: '#22C55E',
      light: '#4ADE80',
      dark: '#16A34A',
      contrastText: '#020617',
    },
    warning: {
      main: '#F59E0B',
      light: '#FBBF24',
      dark: '#D97706',
      contrastText: '#020617',
    },
    error: {
      main: '#EF4444',
      light: '#F87171',
      dark: '#DC2626',
      contrastText: '#FFFFFF',
    },
    info: {
      main: '#3B82F6',
      light: '#60A5FA',
      dark: '#2563EB',
      contrastText: '#FFFFFF',
    },
    background: {
      default: '#020617',
      paper: '#0F1223',
    },
    text: {
      primary: '#F8FAFC',
      secondary: '#94A3B8',
      disabled: '#64748B',
    },
    divider: '#1E293B',
  },
  typography: {
    fontFamily: '"IBM Plex Sans", "Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: { fontWeight: 700, letterSpacing: '-0.02em', color: '#F8FAFC' },
    h2: { fontWeight: 700, letterSpacing: '-0.015em', color: '#F8FAFC' },
    h3: { fontWeight: 600, color: '#F8FAFC' },
    h4: { fontWeight: 600, color: '#F8FAFC' },
    h5: { fontWeight: 600, color: '#F8FAFC' },
    h6: { fontWeight: 600, color: '#F8FAFC', fontSize: '0.875rem' },
    subtitle1: { fontWeight: 500, color: '#F8FAFC' },
    subtitle2: { fontWeight: 500, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.75rem' },
    body1: { fontWeight: 400, color: '#F8FAFC', fontSize: '0.875rem' },
    body2: { fontWeight: 400, color: '#94A3B8', fontSize: '0.875rem' },
    caption: { fontWeight: 500, color: '#64748B', fontSize: '0.75rem' },
    button: { fontWeight: 600, textTransform: 'none', letterSpacing: '0.02em' },
  },
  shape: {
    borderRadius: 6,
  },
  shadows: [
    'none',
    '0 1px 2px rgba(0, 0, 0, 0.4)',
    '0 2px 4px rgba(0, 0, 0, 0.4)',
    '0 4px 8px rgba(0, 0, 0, 0.4)',
    '0 8px 16px rgba(0, 0, 0, 0.4)',
    '0 12px 24px rgba(0, 0, 0, 0.4)',
    '0 16px 32px rgba(0, 0, 0, 0.4)',
    '0 20px 40px rgba(0, 0, 0, 0.4)',
    '0 24px 48px rgba(0, 0, 0, 0.4)',
    '0 28px 56px rgba(0, 0, 0, 0.4)',
    '0 32px 64px rgba(0, 0, 0, 0.4)',
    '0 36px 72px rgba(0, 0, 0, 0.4)',
    '0 40px 80px rgba(0, 0, 0, 0.4)',
    '0 44px 88px rgba(0, 0, 0, 0.4)',
    '0 48px 96px rgba(0, 0, 0, 0.4)',
    '0 52px 104px rgba(0, 0, 0, 0.4)',
    '0 56px 112px rgba(0, 0, 0, 0.4)',
    '0 60px 120px rgba(0, 0, 0, 0.4)',
    '0 64px 128px rgba(0, 0, 0, 0.4)',
    '0 68px 136px rgba(0, 0, 0, 0.4)',
    '0 72px 144px rgba(0, 0, 0, 0.4)',
    '0 76px 152px rgba(0, 0, 0, 0.4)',
    '0 80px 160px rgba(0, 0, 0, 0.4)',
    '0 84px 168px rgba(0, 0, 0, 0.4)',
    '0 88px 176px rgba(0, 0, 0, 0.4)',
  ],
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: '#0F1223',
          border: '1px solid #1E293B',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
          transition: 'box-shadow 200ms ease',
          '&:hover': {
            borderColor: '#334155',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: '#0F1223',
          border: '1px solid #1E293B',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          textTransform: 'none',
          letterSpacing: '0.02em',
          borderRadius: 6,
        },
        containedPrimary: {
          backgroundColor: '#22C55E',
          color: '#020617',
          '&:hover': {
            backgroundColor: '#16A34A',
          },
        },
        outlined: {
          borderWidth: 1,
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            backgroundColor: '#0F1223',
            borderRadius: 6,
            '& fieldset': {
              borderColor: '#334155',
            },
            '&:hover fieldset': {
              borderColor: '#475569',
            },
            '&.Mui-focused fieldset': {
              borderColor: '#22C55E',
              borderWidth: 1,
            },
          },
          '& .MuiInputLabel-root': {
            color: '#64748B',
            fontWeight: 500,
            '&.Mui-focused': {
              color: '#22C55E',
            },
          },
          '& .MuiOutlinedInput-input': {
            padding: '14px 16px',
            color: '#F8FAFC',
          },
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        root: {
          backgroundColor: '#0F1223',
          borderRadius: 6,
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: '#334155',
          },
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: '#475569',
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: '#22C55E',
            borderWidth: 1,
          },
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: {
          backgroundColor: '#0F1223',
          color: '#F8FAFC',
          '&:hover': {
            backgroundColor: 'rgba(34, 197, 94, 0.08)',
          },
          '&.Mui-selected': {
            backgroundColor: 'rgba(34, 197, 94, 0.12)',
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid #1E293B',
          backgroundColor: '#0F1223',
        },
        head: {
          fontWeight: 600,
          color: '#94A3B8',
          textTransform: 'uppercase',
          fontSize: '0.7rem',
          letterSpacing: '0.05em',
          backgroundColor: '#0A0E1A',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:nth-of-type(even)': {
            backgroundColor: '#080C16',
          },
          '&:hover': {
            backgroundColor: 'rgba(34, 197, 94, 0.04)',
          },
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid #1E293B',
        },
        indicator: {
          backgroundColor: '#22C55E',
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          letterSpacing: '0.02em',
          fontWeight: 500,
          color: '#94A3B8',
          '&.Mui-selected': {
            color: '#22C55E',
            fontWeight: 600,
          },
          '&:hover': {
            color: '#4ADE80',
            backgroundColor: 'rgba(34, 197, 94, 0.04)',
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#0F1223',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.4)',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: '#0F1223',
          borderRight: '1px solid #1E293B',
        },
      },
    },
    MuiAvatar: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(34, 197, 94, 0.12)',
          color: '#22C55E',
          border: '1px solid rgba(34, 197, 94, 0.2)',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
          borderRadius: 4,
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 6,
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: '#0F1223',
          border: '1px solid #1E293B',
          boxShadow: '0 24px 48px rgba(0, 0, 0, 0.5)',
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          backgroundColor: '#1E293B',
        },
      },
    },
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: '#020617',
        },
      },
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <CssBaseline />
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ThemeProvider theme={theme}>
        <I18nProvider>
          <App />
        </I18nProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
)

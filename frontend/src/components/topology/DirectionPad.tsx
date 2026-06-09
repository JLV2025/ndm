import { Paper, IconButton, Stack } from '@mui/material'
import {
  KeyboardArrowUp, KeyboardArrowDown, KeyboardArrowLeft, KeyboardArrowRight,
  RestartAlt as ResetIcon,
} from '@mui/icons-material'

interface DirectionPadProps {
  step?: number
  onUp: () => void
  onDown: () => void
  onLeft: () => void
  onRight: () => void
  onReset: () => void
}

export default function DirectionPad({
  step = 10,
  onUp, onDown, onLeft, onRight, onReset,
}: DirectionPadProps) {
  const btnSx = { color: '#94a3b8', p: 0.3 }

  return (
    <Paper
      sx={{
        p: 0.3, borderRadius: 2,
        bgcolor: 'rgba(15, 18, 35, 0.85)', backdropFilter: 'blur(8px)',
        border: '1px solid #334155',
      }}
    >
      <Stack spacing={0.1} alignItems="center">
        <IconButton size="small" onClick={onUp} sx={btnSx}>
          <KeyboardArrowUp fontSize="small" />
        </IconButton>
        <Stack direction="row" spacing={0.1}>
          <IconButton size="small" onClick={onLeft} sx={btnSx}>
            <KeyboardArrowLeft fontSize="small" />
          </IconButton>
          <IconButton size="small" onClick={onReset} sx={{ color: '#64748b', p: 0.3 }}>
            <ResetIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" onClick={onRight} sx={btnSx}>
            <KeyboardArrowRight fontSize="small" />
          </IconButton>
        </Stack>
        <IconButton size="small" onClick={onDown} sx={btnSx}>
          <KeyboardArrowDown fontSize="small" />
        </IconButton>
      </Stack>
    </Paper>
  )
}

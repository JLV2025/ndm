import React from 'react'
import { Box, Typography, ToggleButton, ToggleButtonGroup } from '@mui/material'

const LOCATIONS_ROW1 = ['BJD', 'BJQ', 'DZN', 'PVG', 'SHA', 'SZX', 'ZGN', 'ITM']
const LOCATIONS_ROW2 = ['PEK', 'DEZ', 'UCD', 'SJY']

interface LocationFilterProps {
  selectedLocation: string | null
  onChange: (v: string | null) => void
}

const LocationFilter: React.FC<LocationFilterProps> = React.memo(({ selectedLocation, onChange }) => {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
      <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', mr: 0.5 }}>
        Filter by Location:
      </Typography>
      <ToggleButtonGroup
        value={selectedLocation}
        exclusive
        onChange={(_, v) => onChange(v)}
        size="small"
        sx={{
          display: 'flex', flexWrap: 'wrap', gap: 0.5,
          '& .MuiToggleButton-root': {
            color: 'text.secondary',
            borderColor: 'divider',
            px: 1.5, py: 0.25, fontSize: '0.7rem', fontWeight: 600,
            textTransform: 'none', borderRadius: '6px !important',
            '&.Mui-selected': {
              color: 'primary.main',
              bgcolor: 'rgba(34, 197, 94, 0.1)',
              borderColor: 'rgba(34, 197, 94, 0.3)',
            },
            '&:hover': { bgcolor: 'rgba(34, 197, 94, 0.06)' },
          },
        }}
      >
        {[...LOCATIONS_ROW1, '/', ...LOCATIONS_ROW2].map((loc) =>
          loc === '/' ? (
            <Typography key="sep" variant="caption" sx={{ color: 'text.disabled', alignSelf: 'center', mx: 0.25, fontSize: '0.7rem' }}>/</Typography>
          ) : (
            <ToggleButton key={loc} value={loc}>{loc}</ToggleButton>
          )
        )}
      </ToggleButtonGroup>
    </Box>
  )
})

export default LocationFilter

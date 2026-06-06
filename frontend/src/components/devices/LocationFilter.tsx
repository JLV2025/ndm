import React from 'react'
import { Box, Typography, ToggleButton, ToggleButtonGroup } from '@mui/material'
import { useI18n } from '../../i18n'

interface LocationFilterProps {
  selectedLocation: string | null
  onChange: (v: string | null) => void
  locations: string[]
}

const LocationFilter: React.FC<LocationFilterProps> = React.memo(({ selectedLocation, onChange, locations }) => {
  const { t } = useI18n()
  if (locations.length === 0) return null

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
      <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', mr: 0.5 }}>
        {t('devices.filterByLocation')}:
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
              bgcolor: 'rgba(45, 212, 110, 0.1)',
              borderColor: 'rgba(45, 212, 110, 0.3)',
            },
            '&:hover': { bgcolor: 'rgba(45, 212, 110, 0.06)' },
          },
        }}
      >
        <ToggleButton key="all" value={null}>ALL</ToggleButton>
        {locations.map((loc) => (
          <ToggleButton key={loc} value={loc}>{loc}</ToggleButton>
        ))}
      </ToggleButtonGroup>
    </Box>
  )
})

export default LocationFilter

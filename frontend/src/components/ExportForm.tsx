import { Box, Button, Stack, TextField } from '@mui/material';

/** CSV export (stretch goal): a plain GET form pointed at a Next route handler. */
export function ExportForm({ statuses }: { statuses: string[] }) {
  return (
    <Box component="form" action="/api/export" method="get">
      {statuses.map((status) => (
        <input key={status} type="hidden" name="status" value={status} />
      ))}
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        gap={2}
        alignItems={{ sm: 'flex-end' }}>
        <TextField
          label="From (created)"
          name="from"
          type="date"
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          label="To (created)"
          name="to"
          type="date"
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <Button type="submit" variant="outlined">
          Download CSV
        </Button>
      </Stack>
    </Box>
  );
}

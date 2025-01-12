import { Box, Typography, Paper, Grid } from '@mui/material';

function Dashboard() {
  return (
    <Box sx={{ p: 3 }}>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h5">Dashboard</Typography>
            <Typography variant="body1">Dashboard content coming soon...</Typography>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}

export default Dashboard; 
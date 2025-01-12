import { Box, Typography, Paper, Tabs, Tab } from '@mui/material';
import { useState } from 'react';
import Crawlers from './Crawlers';
import DataExplorer from './DataExplorer';
import Logs from './Logs';

function TabPanel({ children, value, index }) {
  return (
    <div hidden={value !== index} style={{ padding: value === index ? '20px 0' : 0 }}>
      {value === index && children}
    </div>
  );
}

function Dashboard() {
  const [tabValue, setTabValue] = useState(0);

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  return (
    <Box sx={{ p: 3 }}>
      <Paper sx={{ p: 2 }}>
        <Typography variant="h5" gutterBottom>Dashboard</Typography>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label="Crawlers" />
            <Tab label="Data Explorer" />
            <Tab label="Logs" />
          </Tabs>
        </Box>
        <TabPanel value={tabValue} index={0}>
          <Crawlers />
        </TabPanel>
        <TabPanel value={tabValue} index={1}>
          <DataExplorer />
        </TabPanel>
        <TabPanel value={tabValue} index={2}>
          <Logs />
        </TabPanel>
      </Paper>
    </Box>
  );
}

export default Dashboard; 
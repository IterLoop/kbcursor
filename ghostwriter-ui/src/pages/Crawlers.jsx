import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Switch,
  Chip,
  IconButton,
  Tooltip
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import RefreshIcon from '@mui/icons-material/Refresh';

const CRAWLER_TYPES = {
  STATIC: 'Static',
  SELENIUM: 'Selenium',
  APIFY: 'Apify',
  JS: 'JavaScript'
};

const STATUS = {
  IDLE: 'idle',
  RUNNING: 'running',
  ERROR: 'error'
};

function Crawlers() {
  const [crawlers, setCrawlers] = useState([]);
  const [loading, setLoading] = useState(true);

  const columns = [
    { field: 'name', headerName: 'Name', flex: 1 },
    { field: 'type', headerName: 'Type', flex: 1,
      renderCell: (params) => (
        <Chip label={params.value} variant="outlined" />
      )
    },
    { field: 'status', headerName: 'Status', flex: 1,
      renderCell: (params) => (
        <Chip 
          label={params.value}
          color={params.value === STATUS.RUNNING ? 'success' : 
                params.value === STATUS.ERROR ? 'error' : 'default'}
        />
      )
    },
    { field: 'lastRun', headerName: 'Last Run', flex: 1,
      valueFormatter: (params) => new Date(params.value).toLocaleString()
    },
    { field: 'enabled', headerName: 'Enabled', width: 120,
      renderCell: (params) => (
        <Switch
          checked={params.value}
          onChange={(e) => handleToggleEnabled(params.row.id, e.target.checked)}
        />
      )
    },
    { field: 'actions', headerName: 'Actions', width: 120,
      renderCell: (params) => (
        <Box>
          {params.row.status !== STATUS.RUNNING ? (
            <Tooltip title="Start Crawler">
              <IconButton onClick={() => handleStartCrawler(params.row.id)} color="primary">
                <PlayArrowIcon />
              </IconButton>
            </Tooltip>
          ) : (
            <Tooltip title="Stop Crawler">
              <IconButton onClick={() => handleStopCrawler(params.row.id)} color="error">
                <StopIcon />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      )
    }
  ];

  useEffect(() => {
    fetchCrawlers();
  }, []);

  const fetchCrawlers = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API call
      const response = await fetch('/api/v1/crawlers');
      const data = await response.json();
      setCrawlers(data);
    } catch (error) {
      console.error('Error fetching crawlers:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleEnabled = async (id, enabled) => {
    try {
      // TODO: Replace with actual API call
      await fetch(`/api/v1/crawlers/${id}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      fetchCrawlers();
    } catch (error) {
      console.error('Error toggling crawler:', error);
    }
  };

  const handleStartCrawler = async (id) => {
    try {
      // TODO: Replace with actual API call
      await fetch(`/api/v1/crawlers/${id}/start`, {
        method: 'POST'
      });
      fetchCrawlers();
    } catch (error) {
      console.error('Error starting crawler:', error);
    }
  };

  const handleStopCrawler = async (id) => {
    try {
      // TODO: Replace with actual API call
      await fetch(`/api/v1/crawlers/${id}/stop`, {
        method: 'POST'
      });
      fetchCrawlers();
    } catch (error) {
      console.error('Error stopping crawler:', error);
    }
  };

  return (
    <Box sx={{ height: '100%', width: '100%', p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h5" component="h1">
          Crawler Management
        </Typography>
        <Tooltip title="Refresh">
          <IconButton onClick={fetchCrawlers}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>
      
      <Paper sx={{ height: 'calc(100vh - 200px)', width: '100%' }}>
        <DataGrid
          rows={crawlers}
          columns={columns}
          pageSize={10}
          rowsPerPageOptions={[10, 25, 50]}
          checkboxSelection
          disableSelectionOnClick
          loading={loading}
        />
      </Paper>
    </Box>
  );
}

export default Crawlers; 
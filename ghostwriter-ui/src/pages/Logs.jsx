import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  TextField,
  MenuItem,
  Stack
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import RefreshIcon from '@mui/icons-material/Refresh';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { LocalizationProvider, DateTimePicker } from '@mui/x-date-pickers';

const LOG_LEVELS = {
  INFO: 'info',
  WARNING: 'warning',
  ERROR: 'error',
  DEBUG: 'debug'
};

function Logs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    level: '',
    startDate: null,
    endDate: null,
    search: ''
  });

  const columns = [
    { 
      field: 'timestamp', 
      headerName: 'Timestamp', 
      flex: 1,
      valueFormatter: (params) => new Date(params.value).toLocaleString()
    },
    { 
      field: 'level', 
      headerName: 'Level', 
      width: 120,
      renderCell: (params) => (
        <Chip 
          label={params.value}
          color={
            params.value === LOG_LEVELS.ERROR ? 'error' :
            params.value === LOG_LEVELS.WARNING ? 'warning' :
            params.value === LOG_LEVELS.INFO ? 'info' :
            'default'
          }
          variant="outlined"
        />
      )
    },
    { field: 'source', headerName: 'Source', width: 150 },
    { field: 'message', headerName: 'Message', flex: 2 },
    { field: 'details', headerName: 'Details', flex: 1 }
  ];

  useEffect(() => {
    fetchLogs();
  }, [filters]);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API call
      const queryParams = new URLSearchParams({
        level: filters.level,
        startDate: filters.startDate?.toISOString(),
        endDate: filters.endDate?.toISOString(),
        search: filters.search
      }).toString();
      
      const response = await fetch(`/api/v1/logs?${queryParams}`);
      const data = await response.json();
      setLogs(data);
    } catch (error) {
      console.error('Error fetching logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
  };

  return (
    <Box sx={{ height: '100%', width: '100%', p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h5" component="h1">
          System Logs
        </Typography>
        <Tooltip title="Refresh">
          <IconButton onClick={fetchLogs}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
        <TextField
          select
          label="Log Level"
          value={filters.level}
          onChange={(e) => handleFilterChange('level', e.target.value)}
          sx={{ width: 150 }}
        >
          <MenuItem value="">All</MenuItem>
          {Object.entries(LOG_LEVELS).map(([key, value]) => (
            <MenuItem key={value} value={value}>
              {key}
            </MenuItem>
          ))}
        </TextField>

        <LocalizationProvider dateAdapter={AdapterDateFns}>
          <DateTimePicker
            label="Start Date"
            value={filters.startDate}
            onChange={(value) => handleFilterChange('startDate', value)}
            renderInput={(params) => <TextField {...params} />}
          />
          <DateTimePicker
            label="End Date"
            value={filters.endDate}
            onChange={(value) => handleFilterChange('endDate', value)}
            renderInput={(params) => <TextField {...params} />}
          />
        </LocalizationProvider>

        <TextField
          label="Search"
          value={filters.search}
          onChange={(e) => handleFilterChange('search', e.target.value)}
          sx={{ width: 200 }}
        />
      </Stack>
      
      <Paper sx={{ height: 'calc(100vh - 280px)', width: '100%' }}>
        <DataGrid
          rows={logs}
          columns={columns}
          pageSize={25}
          rowsPerPageOptions={[25, 50, 100]}
          disableSelectionOnClick
          loading={loading}
          sortModel={[
            {
              field: 'timestamp',
              sort: 'desc',
            },
          ]}
        />
      </Paper>
    </Box>
  );
}

export default Logs; 
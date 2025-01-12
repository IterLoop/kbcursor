import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Box,
  Tabs,
  Tab,
  Typography,
  Button,
  Paper,
  TextField,
  InputAdornment,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  CircularProgress,
  Alert
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';

function TabPanel(props) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`tabpanel-${index}`}
      aria-labelledby={`tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

export default function DataExplorer() {
  const [currentTab, setCurrentTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDataType, setSelectedDataType] = useState('raw');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // Fetch collections info
  const { data: collectionsData } = useQuery({
    queryKey: ['collections'],
    queryFn: async () => {
      const response = await fetch('/api/v1/data/collections');
      if (!response.ok) throw new Error('Failed to fetch collections');
      return response.json();
    }
  });

  // Fetch content data with pagination
  const { data: contentData, isLoading: isLoadingContent, error: contentError } = useQuery({
    queryKey: ['content', selectedDataType, page, rowsPerPage],
    queryFn: async () => {
      const response = await fetch(`/api/v1/data/content?data_type=${selectedDataType}&page=${page + 1}&limit=${rowsPerPage}`);
      if (!response.ok) throw new Error('Failed to fetch content');
      return response.json();
    }
  });

  // Search query
  const { data: searchData, isLoading: isLoadingSearch } = useQuery({
    queryKey: ['search', searchQuery, selectedDataType],
    queryFn: async () => {
      if (!searchQuery) return null;
      const response = await fetch(`/api/v1/data/search?q=${encodeURIComponent(searchQuery)}&data_type=${selectedDataType}`);
      if (!response.ok) throw new Error('Failed to search');
      return response.json();
    },
    enabled: !!searchQuery
  });

  // Rescrape mutation
  const rescrape = useMutation({
    mutationFn: async (url) => {
      const response = await fetch('/api/v1/data/rescrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      if (!response.ok) throw new Error('Failed to rescrape');
      return response.json();
    }
  });

  const handleTabChange = (event, newValue) => {
    setCurrentTab(newValue);
    setSearchQuery('');
  };

  const handleDataTypeChange = (event) => {
    setSelectedDataType(event.target.value);
    setPage(0);
  };

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleRescrape = (url) => {
    rescrape.mutate(url);
  };

  const renderTable = (data) => {
    if (!data?.documents?.length) {
      return <Alert severity="info">No documents found</Alert>;
    }

    return (
      <>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Title</TableCell>
                <TableCell>URL</TableCell>
                <TableCell>Author</TableCell>
                <TableCell>Source</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.documents.map((doc) => (
                <TableRow key={doc._id}>
                  <TableCell>{doc.title}</TableCell>
                  <TableCell>{doc.url}</TableCell>
                  <TableCell>{doc.metadata?.author}</TableCell>
                  <TableCell>{doc.source}</TableCell>
                  <TableCell>{doc.processing_status}</TableCell>
                  <TableCell>
                    <Button
                      size="small"
                      onClick={() => handleRescrape(doc.url)}
                      disabled={rescrape.isLoading}
                    >
                      Rescrape
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        {contentData && (
          <TablePagination
            component="div"
            count={contentData.total}
            page={page}
            onPageChange={handleChangePage}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={handleChangeRowsPerPage}
          />
        )}
      </>
    );
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={currentTab} onChange={handleTabChange}>
          <Tab label="Search Data" />
          <Tab label="Content Data" />
        </Tabs>
      </Box>

      {/* Collections info */}
      {collectionsData && (
        <Box sx={{ p: 2, display: 'flex', gap: 2 }}>
          <Typography>
            Raw Content: {collectionsData.raw_content} documents
          </Typography>
          <Typography>
            Processed Content: {collectionsData.processed_content} documents
          </Typography>
        </Box>
      )}

      {/* Data type selector */}
      <Box sx={{ p: 2 }}>
        <FormControl sx={{ minWidth: 200 }}>
          <InputLabel>Data Type</InputLabel>
          <Select
            value={selectedDataType}
            onChange={handleDataTypeChange}
            label="Data Type"
          >
            <MenuItem value="raw">Raw Content</MenuItem>
            <MenuItem value="processed">Processed Content</MenuItem>
          </Select>
        </FormControl>
      </Box>

      <TabPanel value={currentTab} index={0}>
        <Paper sx={{ p: 2 }}>
          <Box sx={{ mb: 2 }}>
            <TextField
              fullWidth
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by title, URL, or content..."
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton>
                      <SearchIcon />
                    </IconButton>
                  </InputAdornment>
                )
              }}
            />
          </Box>

          {isLoadingSearch ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
              <CircularProgress />
            </Box>
          ) : (
            searchQuery && searchData && renderTable(searchData)
          )}
        </Paper>
      </TabPanel>

      <TabPanel value={currentTab} index={1}>
        <Paper sx={{ p: 2 }}>
          {isLoadingContent ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
              <CircularProgress />
            </Box>
          ) : contentError ? (
            <Alert severity="error">{contentError.message}</Alert>
          ) : (
            contentData && renderTable(contentData)
          )}
        </Paper>
      </TabPanel>
    </Box>
  );
} 
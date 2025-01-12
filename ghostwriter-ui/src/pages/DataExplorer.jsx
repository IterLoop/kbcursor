import { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Tab,
  Tabs,
  CircularProgress,
  Alert
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';

function TabPanel({ children, value, index }) {
  return value === index ? children : null;
}

export default function DataExplorer() {
  console.log('DataExplorer component rendered');
  const [value, setValue] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const fetchContent = async (type) => {
    const url = `http://localhost:8000/api/v1/data/content?page=${page + 1}&limit=${rowsPerPage}&data_type=${type}`;
    console.log('Fetching data from:', url);
    
    try {
      const response = await fetch(url);
      console.log('Response status:', response.status);
      
      if (!response.ok) {
        throw new Error(`Network response was not ok: ${response.status}`);
      }
      
      const data = await response.json();
      console.log(`Received ${type} data:`, data);
      return data;
    } catch (error) {
      console.error('Error fetching data:', error);
      throw error;
    }
  };

  const rawContentQuery = useQuery({
    queryKey: ['rawContent', page, rowsPerPage],
    queryFn: () => fetchContent('raw'),
    onError: (error) => {
      console.error('Raw content query error:', error);
    }
  });

  const processedContentQuery = useQuery({
    queryKey: ['processedContent', page, rowsPerPage],
    queryFn: () => fetchContent('processed'),
    onError: (error) => {
      console.error('Processed content query error:', error);
    }
  });

  const handleChangePage = (event, newPage) => {
    console.log('Page changed to:', newPage);
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    const newRowsPerPage = parseInt(event.target.value, 10);
    console.log('Rows per page changed to:', newRowsPerPage);
    setRowsPerPage(newRowsPerPage);
    setPage(0);
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString();
  };

  const renderContent = (query, type) => {
    console.log('Rendering content, query status:', query.status);
    
    if (query.isLoading) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      );
    }

    if (query.isError) {
      return (
        <Alert severity="error">
          Error loading data: {query.error.message}
        </Alert>
      );
    }

    const { documents = [], total = 0 } = query.data || {};
    console.log('Rendering documents:', documents.length, 'Total:', total);

    return (
      <>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Title</TableCell>
                <TableCell>URL</TableCell>
                {type === 'raw' && (
                  <>
                    <TableCell>Date</TableCell>
                    <TableCell>Status</TableCell>
                  </>
                )}
                {type === 'processed' && (
                  <>
                    <TableCell>Summary</TableCell>
                    <TableCell>Tags</TableCell>
                  </>
                )}
              </TableRow>
            </TableHead>
            <TableBody>
              {documents.map((item) => (
                <TableRow key={item._id} hover>
                  <TableCell>{item.title || 'No title'}</TableCell>
                  <TableCell>{item.url}</TableCell>
                  {type === 'raw' && (
                    <>
                      <TableCell>{formatDate(item.crawl_time)}</TableCell>
                      <TableCell>{item.status}</TableCell>
                    </>
                  )}
                  {type === 'processed' && (
                    <>
                      <TableCell>{item.summary || 'No summary'}</TableCell>
                      <TableCell>{item.tags ? item.tags.join(', ') : 'No tags'}</TableCell>
                    </>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          rowsPerPageOptions={[5, 10, 25]}
          component="div"
          count={total}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Data Explorer
      </Typography>
      <Paper sx={{ width: '100%' }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={value} onChange={(e, newValue) => setValue(newValue)}>
            <Tab label="Scraped Data" />
            <Tab label="Processed Data" />
          </Tabs>
        </Box>

        <TabPanel value={value} index={0}>
          {renderContent(rawContentQuery, 'raw')}
        </TabPanel>

        <TabPanel value={value} index={1}>
          {renderContent(processedContentQuery, 'processed')}
        </TabPanel>
      </Paper>
    </Box>
  );
} 
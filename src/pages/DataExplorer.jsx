import React from 'react';
import { useQuery } from '@tanstack/react-query';
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
  CircularProgress,
  Alert,
  Tabs,
  Tab
} from '@mui/material';

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
  const [currentTab, setCurrentTab] = React.useState(0);
  const [page, setPage] = React.useState(0);
  const [rowsPerPage, setRowsPerPage] = React.useState(10);

  // Fetch raw content
  const { data: rawData, isLoading: isLoadingRaw, error: rawError } = useQuery({
    queryKey: ['content', 'raw', page, rowsPerPage],
    queryFn: async () => {
      console.log('Fetching raw content...');
      const url = `/api/v1/data/content?data_type=raw&page=${page + 1}&limit=${rowsPerPage}`;
      console.log('Request URL:', url);
      
      const response = await fetch(url);
      console.log('Raw Response:', response);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch raw content: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log('Raw content data:', data);
      return data;
    }
  });

  // Fetch processed content
  const { data: processedData, isLoading: isLoadingProcessed, error: processedError } = useQuery({
    queryKey: ['content', 'processed', page, rowsPerPage],
    queryFn: async () => {
      console.log('Fetching processed content...');
      const url = `/api/v1/data/content?data_type=processed&page=${page + 1}&limit=${rowsPerPage}`;
      console.log('Request URL:', url);
      
      const response = await fetch(url);
      console.log('Processed Response:', response);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch processed content: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log('Processed content data:', data);
      return data;
    }
  });

  const handleChangePage = (event, newPage) => {
    console.log('Changing page to:', newPage);
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    const newRowsPerPage = parseInt(event.target.value, 10);
    console.log('Changing rows per page to:', newRowsPerPage);
    setRowsPerPage(newRowsPerPage);
    setPage(0);
  };

  const renderTable = (data, error) => {
    console.log('Rendering table with data:', data);
    console.log('Error state:', error);

    if (error) {
      console.error('Error rendering table:', error);
      return <Alert severity="error">{error.message}</Alert>;
    }

    if (!data?.documents?.length) {
      console.log('No documents found');
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
                <TableCell>Date</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.documents.map((doc, index) => {
                console.log('Rendering document:', doc);
                return (
                  <TableRow key={doc._id || doc.url || index}>
                    <TableCell>{doc.title || 'No title'}</TableCell>
                    <TableCell>{doc.url || 'No URL'}</TableCell>
                    <TableCell>
                      {doc.crawl_time ? new Date(doc.crawl_time).toLocaleString() : 'No date'}
                    </TableCell>
                    <TableCell>{doc.status || 'No status'}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={data.total || 0}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </>
    );
  };

  console.log('Current tab:', currentTab);
  console.log('Raw data state:', { data: rawData, loading: isLoadingRaw, error: rawError });
  console.log('Processed data state:', { data: processedData, loading: isLoadingProcessed, error: processedError });

  return (
    <Box sx={{ width: '100%' }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={currentTab} onChange={(e, newValue) => {
          console.log('Changing tab to:', newValue);
          setCurrentTab(newValue);
        }}>
          <Tab label={`Scraped Data (${rawData?.total || 0})`} />
          <Tab label={`Processed Data (${processedData?.total || 0})`} />
        </Tabs>
      </Box>

      <TabPanel value={currentTab} index={0}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Scraped Data
          </Typography>
          {isLoadingRaw ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
              <CircularProgress />
            </Box>
          ) : (
            renderTable(rawData, rawError)
          )}
        </Paper>
      </TabPanel>

      <TabPanel value={currentTab} index={1}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Processed Data
          </Typography>
          {isLoadingProcessed ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
              <CircularProgress />
            </Box>
          ) : (
            renderTable(processedData, processedError)
          )}
        </Paper>
      </TabPanel>
    </Box>
  );
} 
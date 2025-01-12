import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  LinearProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Pagination
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import AutorenewIcon from '@mui/icons-material/Autorenew';

function DataExplorer() {
  const [content, setContent] = useState([]);
  const [selectedContent, setSelectedContent] = useState(null);
  const [pipelineTasks, setPipelineTasks] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [status, setStatus] = useState('');
  const [source, setSource] = useState('');
  const [detailOpen, setDetailOpen] = useState(false);
  
  const fetchContent = async () => {
    try {
      const params = new URLSearchParams({
        page,
        limit: 10,
        ...(status && { status }),
        ...(source && { source })
      });
      console.log('Fetching content with params:', params.toString());
      const response = await fetch(`http://localhost:8000/api/v1/data/content?${params}`);
      const data = await response.json();
      console.log('Received data:', data);
      setContent(data);
      setTotalPages(Math.ceil(data.length / 10));
    } catch (error) {
      console.error('Error fetching content:', error);
    }
  };

  const fetchPipelineStatus = async () => {
    try {
      console.log('Fetching pipeline status');
      const response = await fetch('http://localhost:8000/api/v1/data/pipeline/status');
      const data = await response.json();
      console.log('Received pipeline status:', data);
      setPipelineTasks(data);
    } catch (error) {
      console.error('Error fetching pipeline status:', error);
    }
  };

  const handleContentClick = async (contentId) => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/data/content/${contentId}`);
      const data = await response.json();
      console.log('Content detail:', data);
      setSelectedContent(data);
      setDetailOpen(true);
    } catch (error) {
      console.error('Error fetching content detail:', error);
    }
  };

  const handleReprocess = async (contentId) => {
    try {
      await fetch(`http://localhost:8000/api/v1/data/content/${contentId}/reprocess`, {
        method: 'POST'
      });
      fetchPipelineStatus();
    } catch (error) {
      console.error('Error reprocessing content:', error);
    }
  };

  useEffect(() => {
    console.log('DataExplorer mounted or dependencies changed');
    fetchContent();
    const interval = setInterval(fetchPipelineStatus, 5000);
    return () => {
      console.log('Cleaning up interval');
      clearInterval(interval);
    };
  }, [page, status, source]);

  const getStatusColor = (status) => {
    const colors = {
      processed: 'success',
      raw: 'default',
      processing: 'warning',
      failed: 'error'
    };
    return colors[status] || 'default';
  };

  return (
    <Box sx={{ p: 3 }}>
      <Grid container spacing={3}>
        {/* Pipeline Status */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom>
              AI Pipeline Status
            </Typography>
            <Grid container spacing={2}>
              {pipelineTasks.map((task) => (
                <Grid item xs={12} sm={6} md={4} key={task.task_id}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="subtitle2">{task.task_type}</Typography>
                    <Typography variant="body2" color="textSecondary">
                      Content: {task.content_id}
                    </Typography>
                    <LinearProgress 
                      variant="determinate" 
                      value={task.progress * 100} 
                      sx={{ my: 1 }}
                    />
                    <Typography variant="body2">
                      {Math.round(task.progress * 100)}% Complete
                    </Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </Paper>
        </Grid>

        {/* Content List */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6">Content Explorer</Typography>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Status</InputLabel>
                  <Select
                    value={status}
                    label="Status"
                    onChange={(e) => setStatus(e.target.value)}
                  >
                    <MenuItem value="">All</MenuItem>
                    <MenuItem value="processed">Processed</MenuItem>
                    <MenuItem value="raw">Raw</MenuItem>
                    <MenuItem value="processing">Processing</MenuItem>
                    <MenuItem value="failed">Failed</MenuItem>
                  </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Source</InputLabel>
                  <Select
                    value={source}
                    label="Source"
                    onChange={(e) => setSource(e.target.value)}
                  >
                    <MenuItem value="">All</MenuItem>
                    <MenuItem value="web">Web</MenuItem>
                    <MenuItem value="pdf">PDF</MenuItem>
                    <MenuItem value="social">Social</MenuItem>
                    <MenuItem value="news">News</MenuItem>
                  </Select>
                </FormControl>
                <Button
                  startIcon={<RefreshIcon />}
                  onClick={fetchContent}
                  variant="outlined"
                >
                  Refresh
                </Button>
              </Box>
            </Box>

            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Title</TableCell>
                    <TableCell>URL</TableCell>
                    <TableCell>Date</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Source</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {content.map((item) => (
                    <TableRow key={item.url} hover>
                      <TableCell>{item.title}</TableCell>
                      <TableCell>{item.url}</TableCell>
                      <TableCell>
                        {new Date(item.date_crawled).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={item.processing_status}
                          color={getStatusColor(item.processing_status)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>{item.source}</TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          onClick={() => handleContentClick(item._id)}
                        >
                          View
                        </Button>
                        <Button
                          size="small"
                          startIcon={<AutorenewIcon />}
                          onClick={() => handleReprocess(item._id)}
                          disabled={item.processing_status === 'processing'}
                        >
                          Reprocess
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={(e, value) => setPage(value)}
              />
            </Box>
          </Paper>
        </Grid>
      </Grid>

      {/* Detail Dialog */}
      <Dialog
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        {selectedContent && (
          <>
            <DialogTitle>
              Content Details: {selectedContent.raw_content.title || 'No Title'}
            </DialogTitle>
            <DialogContent dividers>
              <Grid container spacing={3}>
                {/* Raw Content Section */}
                <Grid item xs={12}>
                  <Paper sx={{ p: 2, mb: 2 }}>
                    <Typography variant="h6" gutterBottom>Raw Content</Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={12} md={6}>
                        <Typography variant="subtitle2">URL</Typography>
                        <Typography variant="body2" sx={{ mb: 2 }}>
                          {selectedContent.raw_content.url}
                        </Typography>

                        <Typography variant="subtitle2">Date Crawled</Typography>
                        <Typography variant="body2" sx={{ mb: 2 }}>
                          {new Date(selectedContent.raw_content.date_crawled).toLocaleString()}
                        </Typography>

                        <Typography variant="subtitle2">Source</Typography>
                        <Typography variant="body2" sx={{ mb: 2 }}>
                          {selectedContent.raw_content.source}
                        </Typography>

                        <Typography variant="subtitle2">Content Hash</Typography>
                        <Typography variant="body2" sx={{ mb: 2 }}>
                          {selectedContent.raw_content.content_hash || 'Not available'}
                        </Typography>
                      </Grid>
                      <Grid item xs={12}>
                        <Typography variant="subtitle2">Raw Text</Typography>
                        <Paper 
                          variant="outlined" 
                          sx={{ p: 2, maxHeight: 200, overflow: 'auto' }}
                        >
                          <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
                            {selectedContent.raw_content.text || 'No text available'}
                          </Typography>
                        </Paper>
                      </Grid>
                      {selectedContent.raw_content.metadata && (
                        <Grid item xs={12}>
                          <Typography variant="subtitle2">Metadata</Typography>
                          <Paper 
                            variant="outlined" 
                            sx={{ p: 2, maxHeight: 200, overflow: 'auto' }}
                          >
                            <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
                              {JSON.stringify(selectedContent.raw_content.metadata, null, 2)}
                            </Typography>
                          </Paper>
                        </Grid>
                      )}
                    </Grid>
                  </Paper>
                </Grid>

                {/* Processed Content Section */}
                {selectedContent.processed_content && (
                  <Grid item xs={12}>
                    <Paper sx={{ p: 2 }}>
                      <Typography variant="h6" gutterBottom>Processed Content</Typography>
                      <Grid container spacing={2}>
                        <Grid item xs={12}>
                          <Typography variant="subtitle2">Summary</Typography>
                          <Typography variant="body2" sx={{ mb: 2 }}>
                            {selectedContent.processed_content.summary || 'No summary available'}
                          </Typography>
                        </Grid>

                        <Grid item xs={12}>
                          <Typography variant="subtitle2">Processed Text</Typography>
                          <Paper 
                            variant="outlined" 
                            sx={{ p: 2, maxHeight: 200, overflow: 'auto' }}
                          >
                            <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
                              {selectedContent.processed_content.text || 'No processed text available'}
                            </Typography>
                          </Paper>
                        </Grid>

                        {selectedContent.processed_content.tags && selectedContent.processed_content.tags.length > 0 && (
                          <Grid item xs={12}>
                            <Typography variant="subtitle2">Tags</Typography>
                            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                              {selectedContent.processed_content.tags.map((tag) => (
                                <Chip key={tag} label={tag} size="small" />
                              ))}
                            </Box>
                          </Grid>
                        )}

                        {selectedContent.processed_content.classifications && (
                          <Grid item xs={12}>
                            <Typography variant="subtitle2">Classifications</Typography>
                            <Paper 
                              variant="outlined" 
                              sx={{ p: 2, maxHeight: 200, overflow: 'auto' }}
                            >
                              <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
                                {JSON.stringify(selectedContent.processed_content.classifications, null, 2)}
                              </Typography>
                            </Paper>
                          </Grid>
                        )}

                        <Grid item xs={12}>
                          <Typography variant="subtitle2">Processed Date</Typography>
                          <Typography variant="body2">
                            {selectedContent.processed_content.processed_date ? 
                              new Date(selectedContent.processed_content.processed_date).toLocaleString() :
                              'Not available'
                            }
                          </Typography>
                        </Grid>
                      </Grid>
                    </Paper>
                  </Grid>
                )}
              </Grid>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setDetailOpen(false)}>Close</Button>
              {selectedContent.raw_content.processing_status !== 'processing' && (
                <Button 
                  onClick={() => handleReprocess(selectedContent.raw_content._id)}
                  startIcon={<AutorenewIcon />}
                >
                  Reprocess
                </Button>
              )}
            </DialogActions>
          </>
        )}
      </Dialog>
    </Box>
  );
}

export default DataExplorer; 
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
      const response = await fetch(`http://localhost:8000/api/v1/data/content?${params}`);
      const data = await response.json();
      setContent(data);
      setTotalPages(Math.ceil(data.length / 10));
    } catch (error) {
      console.error('Error fetching content:', error);
    }
  };

  const fetchPipelineStatus = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/data/pipeline/status');
      const data = await response.json();
      setPipelineTasks(data);
    } catch (error) {
      console.error('Error fetching pipeline status:', error);
    }
  };

  const handleContentClick = async (contentId) => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/data/content/${contentId}`);
      const data = await response.json();
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
    fetchContent();
    const interval = setInterval(fetchPipelineStatus, 5000);
    return () => clearInterval(interval);
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
                          onClick={() => handleContentClick(item.url)}
                        >
                          View
                        </Button>
                        <Button
                          size="small"
                          startIcon={<AutorenewIcon />}
                          onClick={() => handleReprocess(item.url)}
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
        maxWidth="md"
        fullWidth
      >
        {selectedContent && (
          <>
            <DialogTitle>{selectedContent.title}</DialogTitle>
            <DialogContent dividers>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <Typography variant="subtitle1">Summary</Typography>
                  <Typography variant="body2">{selectedContent.summary}</Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="subtitle1">Full Text</Typography>
                  <Typography variant="body2">{selectedContent.full_text}</Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="subtitle1">Tags</Typography>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    {selectedContent.tags.map((tag) => (
                      <Chip key={tag} label={tag} size="small" />
                    ))}
                  </Box>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="subtitle1">Classifications</Typography>
                  <Grid container spacing={1}>
                    {Object.entries(selectedContent.classifications).map(([key, value]) => (
                      <Grid item xs={6} key={key}>
                        <Paper sx={{ p: 1 }}>
                          <Typography variant="caption" display="block">
                            {key}
                          </Typography>
                          <Typography variant="body2">
                            {typeof value === 'number' ? value.toFixed(2) : value}
                          </Typography>
                        </Paper>
                      </Grid>
                    ))}
                  </Grid>
                </Grid>
              </Grid>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setDetailOpen(false)}>Close</Button>
              <Button
                startIcon={<AutorenewIcon />}
                onClick={() => handleReprocess(selectedContent.url)}
                disabled={selectedContent.processing_status === 'processing'}
              >
                Reprocess
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </Box>
  );
}

export default DataExplorer; 
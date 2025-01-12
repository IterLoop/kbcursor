import React, { useState, useEffect } from 'react';
import { Box, Grid, Paper, Typography, Container } from '@mui/material';
import { styled } from '@mui/material/styles';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

// Styled components
const Item = styled(Paper)(({ theme }) => ({
  backgroundColor: theme.palette.mode === 'dark' ? '#1A2027' : '#fff',
  ...theme.typography.body2,
  padding: theme.spacing(2),
  textAlign: 'center',
  color: theme.palette.text.secondary,
  height: '100%',
}));

// Placeholder data - will be replaced with API data
const initialMetrics = {
  activeCrawlers: 5,
  urlsProcessed: 1250,
  averageProcessingTime: '2.3s',
  dailyStats: {
    processed: [65, 75, 85, 95, 105, 115, 125],
    dates: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  }
};

const Dashboard = () => {
  const [metrics, setMetrics] = useState(initialMetrics);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch('/api/v1/metrics');
        const data = await response.json();
        setMetrics(data);
      } catch (error) {
        console.error('Error fetching metrics:', error);
        // Keep using placeholder data on error
      }
    };

    // Fetch initial data
    fetchMetrics();

    // Set up polling every 30 seconds
    const interval = setInterval(fetchMetrics, 30000);

    return () => clearInterval(interval);
  }, []);

  // Transform data for the chart
  const chartData = metrics.dailyStats.dates.map((date, index) => ({
    date,
    processed: metrics.dailyStats.processed[index],
  }));

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        System Dashboard
      </Typography>
      <Grid container spacing={3}>
        {/* Active Crawlers */}
        <Grid item xs={12} sm={6} md={4}>
          <Item>
            <Typography variant="h6" gutterBottom>
              Active Crawlers
            </Typography>
            <Typography variant="h3">
              {metrics.activeCrawlers}
            </Typography>
          </Item>
        </Grid>

        {/* URLs Processed */}
        <Grid item xs={12} sm={6} md={4}>
          <Item>
            <Typography variant="h6" gutterBottom>
              URLs Processed
            </Typography>
            <Typography variant="h3">
              {metrics.urlsProcessed}
            </Typography>
          </Item>
        </Grid>

        {/* Average Processing Time */}
        <Grid item xs={12} sm={6} md={4}>
          <Item>
            <Typography variant="h6" gutterBottom>
              Avg. Processing Time
            </Typography>
            <Typography variant="h3">
              {metrics.averageProcessingTime}
            </Typography>
          </Item>
        </Grid>

        {/* Processing History Chart */}
        <Grid item xs={12}>
          <Item>
            <Typography variant="h6" gutterBottom>
              Processing History
            </Typography>
            <Box sx={{ height: 300, width: '100%' }}>
              <ResponsiveContainer>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Line 
                    type="monotone" 
                    dataKey="processed" 
                    stroke="#8884d8" 
                    name="URLs Processed"
                  />
                </LineChart>
              </ResponsiveContainer>
            </Box>
          </Item>
        </Grid>
      </Grid>
    </Container>
  );
};

export default Dashboard; 
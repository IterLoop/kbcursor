import { Box, Typography, Container, TextField, FormControl, InputLabel, Select, MenuItem, Slider, Button, Paper, CircularProgress, RadioGroup, FormControlLabel, Radio } from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useState } from 'react';
import { format, subMonths, subWeeks } from 'date-fns';

function ArticleOutline() {
  const [outline, setOutline] = useState('');
  const [audience, setAudience] = useState('');
  const [writingStyle, setWritingStyle] = useState('');
  const [imaginationLevel, setImaginationLevel] = useState(3);
  const [researchLevel, setResearchLevel] = useState(3);
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  
  // Date range states
  const [dateRangeType, setDateRangeType] = useState('relative'); // 'relative' or 'custom'
  const [relativePeriod, setRelativePeriod] = useState('3m'); // '1w', '1m', '3m', '6m'
  const [startDate, setStartDate] = useState(null);
  const [endDate, setEndDate] = useState(null);

  const handleOutlineChange = (event) => {
    setOutline(event.target.value);
  };

  const handleAudienceChange = (event) => {
    setAudience(event.target.value);
  };

  const handleWritingStyleChange = (event) => {
    setWritingStyle(event.target.value);
  };

  const handleImaginationLevelChange = (event, newValue) => {
    setImaginationLevel(newValue);
  };

  const handleResearchLevelChange = (event, newValue) => {
    setResearchLevel(newValue);
  };

  const handleDateRangeTypeChange = (event) => {
    setDateRangeType(event.target.value);
  };

  const handleRelativePeriodChange = (event) => {
    setRelativePeriod(event.target.value);
  };

  const getDateRange = () => {
    if (dateRangeType === 'relative') {
      const endDate = new Date();
      let startDate;

      switch (relativePeriod) {
        case '1w':
          startDate = subWeeks(endDate, 1);
          break;
        case '1m':
          startDate = subMonths(endDate, 1);
          break;
        case '3m':
          startDate = subMonths(endDate, 3);
          break;
        case '6m':
          startDate = subMonths(endDate, 6);
          break;
        default:
          startDate = subMonths(endDate, 3);
      }

      return {
        start: format(startDate, 'yyyy-MM-dd'),
        end: format(endDate, 'yyyy-MM-dd')
      };
    } else {
      // Custom date range
      if (!startDate || !endDate) {
        throw new Error('Please select both start and end dates');
      }
      return {
        start: format(startDate, 'yyyy-MM-dd'),
        end: format(endDate, 'yyyy-MM-dd')
      };
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      const dateRange = getDateRange();
      const response = await fetch('http://localhost:8000/api/v1/articles/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          outline,
          audience,
          writing_style: writingStyle,
          imagination_level: imaginationLevel,
          research_level: researchLevel,
          date_range: dateRange
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate article prompt');
      }

      const data = await response.json();
      setResponse(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ mt: 6, mb: 4, textAlign: 'center' }}>
        <Typography variant="h3" component="h1" gutterBottom>
          Article Outline
        </Typography>
        <Typography variant="subtitle1" color="text.secondary" paragraph>
          Fill in the details below to generate an agent prompt and search terms.
        </Typography>
      </Box>
      <Box component="form" sx={{ mt: 4, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <TextField
          multiline
          rows={8}
          value={outline}
          onChange={handleOutlineChange}
          fullWidth
          sx={{ mb: 4, width: '100%' }}
        />
        <FormControl sx={{ mb: 4, width: '100%' }}>
          <InputLabel>Audience</InputLabel>
          <Select value={audience} onChange={handleAudienceChange}>
            <MenuItem value="general">General</MenuItem>
            <MenuItem value="technical">Technical</MenuItem>
            <MenuItem value="academic">Academic</MenuItem>
          </Select>
        </FormControl>
        <FormControl sx={{ mb: 4, width: '100%' }}>
          <InputLabel>Writing Style</InputLabel>
          <Select value={writingStyle} onChange={handleWritingStyleChange}>
            <MenuItem value="formal">Formal</MenuItem>
            <MenuItem value="casual">Casual</MenuItem>
            <MenuItem value="persuasive">Persuasive</MenuItem>
          </Select>
        </FormControl>
        <Box sx={{ mb: 4, width: '100%' }}>
          <Typography variant="subtitle1" gutterBottom>Imagination Level</Typography>
          <Slider
            value={imaginationLevel}
            onChange={handleImaginationLevelChange}
            step={1}
            marks
            min={1}
            max={5}
            valueLabelDisplay="auto"
          />
        </Box>
        <Box sx={{ mb: 4, width: '100%' }}>
          <Typography variant="subtitle1" gutterBottom>Research Level</Typography>
          <Slider
            value={researchLevel}
            onChange={handleResearchLevelChange}
            step={1}
            marks
            min={1}
            max={5}
            valueLabelDisplay="auto"
          />
        </Box>
        <Box sx={{ mb: 4, width: '100%' }}>
          <Typography variant="subtitle1" gutterBottom>Date Range</Typography>
          <RadioGroup
            value={dateRangeType}
            onChange={handleDateRangeTypeChange}
            sx={{ mb: 2 }}
          >
            <FormControlLabel value="relative" control={<Radio />} label="Quick Select" />
            <FormControlLabel value="custom" control={<Radio />} label="Custom Range" />
          </RadioGroup>

          {dateRangeType === 'relative' ? (
            <FormControl fullWidth>
              <Select
                value={relativePeriod}
                onChange={handleRelativePeriodChange}
                sx={{ mb: 2 }}
              >
                <MenuItem value="1w">Last Week</MenuItem>
                <MenuItem value="1m">Last Month</MenuItem>
                <MenuItem value="3m">Last 3 Months</MenuItem>
                <MenuItem value="6m">Last 6 Months</MenuItem>
              </Select>
            </FormControl>
          ) : (
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <DatePicker
                  label="Start Date"
                  value={startDate}
                  onChange={setStartDate}
                  sx={{ flex: 1 }}
                />
                <DatePicker
                  label="End Date"
                  value={endDate}
                  onChange={setEndDate}
                  minDate={startDate}
                  sx={{ flex: 1 }}
                />
              </Box>
            </LocalizationProvider>
          )}
        </Box>
        <Button 
          variant="contained" 
          size="large" 
          sx={{ mt: 2, mb: 4 }}
          onClick={handleSubmit}
          disabled={loading || !outline || !audience || !writingStyle || (dateRangeType === 'custom' && (!startDate || !endDate))}
        >
          {loading ? <CircularProgress size={24} color="inherit" /> : 'Generate Agent Prompt'}
        </Button>

        {error && (
          <Typography color="error" sx={{ mt: 2 }}>
            Error: {error}
          </Typography>
        )}

        {response && (
          <Paper sx={{ p: 3, width: '100%', mt: 4 }}>
            <Typography variant="h6" gutterBottom>Generated Agent Prompt:</Typography>
            <Typography sx={{ whiteSpace: 'pre-wrap', mb: 4 }}>
              {response.agent_prompt}
            </Typography>
            
            <Typography variant="h6" gutterBottom>Search Terms:</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
              {response.search_terms.map((term, index) => (
                <Paper key={index} sx={{ p: 1 }} variant="outlined">
                  {term}
                </Paper>
              ))}
            </Box>

            <Typography variant="h6" gutterBottom>Date Range:</Typography>
            <Typography>
              From: {response.date_range.start} To: {response.date_range.end}
            </Typography>
          </Paper>
        )}
      </Box>
    </Container>
  );
}

export default ArticleOutline; 
import { Box, Typography, Container } from '@mui/material';

function ArticleOutline() {
  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Article Outline
        </Typography>
      </Box>
    </Container>
  );
}

export default ArticleOutline; 
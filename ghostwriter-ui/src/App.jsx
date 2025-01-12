import { useState } from "react";
import { Box, CssBaseline, ThemeProvider } from "@mui/material";
import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";
import theme from "./theme/theme";

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: "flex" }}>
        <Navbar sidebarOpen={sidebarOpen} toggleSidebar={toggleSidebar} />
        <Sidebar open={sidebarOpen} />
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: 3,
            mt: 8,
            backgroundColor: (theme) => theme.palette.background.default,
          }}
        >
          {/* Main content will go here */}
          <h1>Welcome to Ghostwriter</h1>
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default App;

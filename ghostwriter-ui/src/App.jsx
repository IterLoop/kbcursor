import { useState } from "react";
import { Box, CssBaseline, ThemeProvider, useTheme, useMediaQuery } from "@mui/material";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Crawlers from "./pages/Crawlers";
import Logs from "./pages/Logs";
import theme from "./theme/theme";

const drawerWidth = 240;

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <Router>
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
              width: { sm: `calc(100% - ${sidebarOpen ? drawerWidth : 0}px)` },
              marginLeft: { xs: 0, sm: 0 },
              transition: theme.transitions.create(['margin', 'width'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.leavingScreen,
              }),
              backgroundColor: (theme) => theme.palette.background.default,
            }}
          >
            <Routes>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/crawlers" element={<Crawlers />} />
              <Route path="/logs" element={<Logs />} />
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </Box>
        </Box>
      </ThemeProvider>
    </Router>
  );
}

export default App;

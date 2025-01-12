# Ghostwriter UI

Version: 0.1.0

A modern, responsive user interface for the Ghostwriter content management system.

## Project Structure

```
ghostwriter-ui/
├── src/
│   ├── assets/        # Static assets (images, icons, etc.)
│   ├── components/    # Reusable UI components
│   ├── layouts/       # Layout components and templates
│   ├── pages/         # Page components for each route
│   └── theme/         # Theme configuration and styling
```

## Technology Stack

- React 18.2.0
- Vite 6.0.7
- Material UI 5.15.5
- Emotion (for styled components)

## Features

- Modern, responsive design that works on all devices
- Material Design-based UI components
- Consistent styling and theming
- Navigation:
  - Dashboard
  - Crawlers
  - Data Explorer
  - Logs
  - Settings

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start development server:
   ```bash
   npm run dev
   ```

3. Build for production:
   ```bash
   npm run build
   ```

## Design Decisions

- **Material UI**: Chosen for its comprehensive component library, customization options, and built-in responsive design features
- **Component Structure**: Organized into reusable components for maintainability and consistency
- **Responsive Layout**: Uses Material UI's responsive components and CSS Grid/Flexbox for optimal display across devices
- **Theme Configuration**: Centralized theme configuration for consistent styling

## Version History

- 0.1.0: Initial release
  - Basic project structure
  - Core layout implementation
  - Material UI integration
  - Responsive design implementation 
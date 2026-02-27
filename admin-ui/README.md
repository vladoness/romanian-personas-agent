# Persona Admin UI

React-based admin interface for creating and managing Romanian historical personas.

## Features

- **Authentication**: HTTP Basic Auth with password protection
- **Persona Management**: Create, view, and delete personas
- **File Upload**: Upload works, quotes, and profile documents
- **Ingestion Monitoring**: Real-time progress tracking with auto-refresh
- **Multi-step Workflow**: Guided persona creation process
- **Responsive Design**: Works on desktop and tablet

## Prerequisites

- Node.js 16+ and npm
- FastAPI backend running on http://localhost:8000
- Admin password configured in backend

## Installation

```bash
cd admin-ui
npm install
```

## Running

```bash
npm run dev
```

The admin UI will be available at http://localhost:3001

## First Time Setup

1. Start the FastAPI backend:
   ```bash
   cd ..
   uvicorn api.main:app --reload
   ```

2. Start the admin UI:
   ```bash
   cd admin-ui
   npm run dev
   ```

3. Open http://localhost:3001 in your browser

4. Enter the admin password (configured via `ADMIN_PASSWORD` env var in backend)

## Project Structure

```
admin-ui/
├── index.html              # HTML template
├── package.json            # Dependencies
├── vite.config.js          # Vite configuration
└── src/
    ├── index.jsx           # Entry point
    ├── App.jsx             # Main app with routing
    ├── App.css             # Global styles
    ├── components/         # Reusable components
    │   ├── PersonaForm.jsx
    │   ├── FileUploader.jsx
    │   └── IngestionStatus.jsx
    ├── pages/              # Page components
    │   ├── Dashboard.jsx
    │   ├── CreatePersona.jsx
    │   └── PersonaDetail.jsx
    └── services/           # API client
        └── api.js
```

## Usage Guide

### Creating a Persona

1. Click "Create New Persona" from dashboard
2. Fill in basic information:
   - Persona ID (unique, lowercase, alphanumeric)
   - Display name
   - Birth/death years
   - Description
   - Speaking style
   - Key themes
   - Voice prompt
   - Representative quotes
   - Color (UI accent)
3. Upload files:
   - Works: .txt, .md files (poems, essays, speeches)
   - Quotes: .jsonl files (one quote per line)
   - Profile: .txt, .md, .pdf files (biographical documents)
4. Trigger ingestion
5. Monitor progress (auto-refreshes every 3 seconds)
6. Complete when all jobs finish

### Managing Personas

- **View All**: Dashboard shows all personas with stats
- **View Details**: Click any persona card to see full information
- **Upload Files**: Use the "Upload" tab in persona detail
- **Monitor Ingestion**: Use the "Ingestion Status" tab
- **Retry Failed Jobs**: Click "Retry Failed Jobs" button
- **Delete Persona**: Use "Delete" button (requires confirmation)

### File Formats

**Works** (.txt, .md):
```
Text of literary work...
```

**Quotes** (.jsonl):
```jsonl
{"quote": "Text of quote", "source": "Optional source"}
{"quote": "Another quote", "source": "Source info"}
```

**Profile** (.txt, .md, .pdf):
```
Biographical text or PDF document...
```

## API Client

The `api.js` service handles all backend communication:

- **Authentication**: Stores admin password in localStorage
- **Auto-retry**: Automatically includes auth header
- **Error Handling**: Transforms API errors to user-friendly messages
- **Base URL**: http://localhost:8000

## Development

### Building for Production

```bash
npm run build
```

Output will be in `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## Environment Variables

The admin UI connects to the backend via proxy (configured in `vite.config.js`).

To change the backend URL, edit `vite.config.js`:

```js
server: {
  proxy: {
    '/api': {
      target: 'http://your-backend-url',
      changeOrigin: true
    }
  }
}
```

## Authentication

The UI uses HTTP Basic Auth:
- Username: `admin` (hardcoded)
- Password: Stored in localStorage after first login
- Password is sent with every API request

To log out, click the "Logout" button in the navbar.

## Troubleshooting

### Cannot connect to backend

- Ensure FastAPI is running: `uvicorn api.main:app --reload`
- Check backend is on port 8000
- Check CORS is configured for http://localhost:3001

### Authentication fails

- Verify `ADMIN_PASSWORD` is set in backend `.env`
- Check browser console for error messages
- Try clearing localStorage and logging in again

### File upload fails

- Check file extensions match allowed types
- Ensure persona exists and is in correct status
- Check backend logs for detailed errors

### Ingestion not progressing

- Verify Celery workers are running
- Check Redis is accessible
- Look at backend logs for worker errors
- Use "Retry Failed Jobs" button if any jobs failed

## Tech Stack

- **React 18**: UI library
- **React Router 6**: Client-side routing
- **Vite**: Build tool (fast dev server, optimized builds)
- **Axios**: HTTP client
- **CSS**: Custom styling (no framework dependencies)

## Browser Support

- Chrome/Edge: Latest 2 versions
- Firefox: Latest 2 versions
- Safari: Latest 2 versions

## License

Part of the Romanian Personas Agent project.

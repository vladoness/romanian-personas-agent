# Admin UI Quick Start

## 1. Start Backend (Terminal 1)

```bash
cd /Users/vladsorici/Jira-general/romanian-personas-agent
source .venv/bin/activate
uvicorn api.main:app --reload
```

Backend runs on: http://localhost:8000

## 2. Start Admin UI (Terminal 2)

```bash
cd /Users/vladsorici/Jira-general/romanian-personas-agent/admin-ui
npm run dev
```

Admin UI runs on: http://localhost:3001

## 3. Login

- Open http://localhost:3001
- Enter admin password (from backend `.env` file)
- Password is stored in browser

## 4. Create Your First Persona

### Step 1: Fill Form
- Persona ID: `test_persona` (lowercase, no spaces)
- Display Name: `Test Persona`
- Birth Year: `1900`
- Death Year: `2000` (optional)
- Description: Brief bio
- Speaking Style: Writing characteristics
- Key Themes: Main topics
- Voice Prompt: System prompt for Claude
- Quotes: Add at least one representative quote
- Color: Pick UI accent color

### Step 2: Upload Files

**Works** (.txt or .md):
- Create `test_work.txt` with sample text
- Upload via "Literary Works" section

**Quotes** (.jsonl):
- Create `test_quotes.jsonl`:
  ```jsonl
  {"quote": "This is a test quote", "source": "Test Source"}
  ```
- Upload via "Quotes" section

**Profile** (.txt, .md, or .pdf):
- Create `test_profile.txt` with biographical text
- Upload via "Profile Documents" section

### Step 3: Trigger Ingestion
- Click "Proceed to Ingestion"
- Watch progress bars (auto-refreshes every 3s)
- Wait for all jobs to complete

### Step 4: Success
- View persona details
- Or go back to dashboard

## 5. Common Operations

### View All Personas
- Dashboard shows all personas
- Click any card to view details

### Upload More Files
- Go to persona detail page
- Click "Upload" tab
- Upload additional files

### Monitor Ingestion
- Go to persona detail page
- Click "Ingestion Status" tab
- Progress updates automatically

### Delete Persona
- Go to persona detail page
- Click "Delete Persona"
- Confirm deletion

## 6. Troubleshooting

### Cannot Login
- Check backend is running on port 8000
- Verify `ADMIN_PASSWORD` is set in backend `.env`
- Try clearing browser localStorage

### Cannot Create Persona
- Check form validation errors
- Ensure persona ID is unique
- Check backend logs for errors

### File Upload Fails
- Verify file extensions (.txt, .md for works)
- Check file isn't too large
- Ensure persona exists

### Ingestion Stuck
- Check Celery workers are running: `celery -A workers.celery_app worker --loglevel=info`
- Check Redis is running: `redis-cli ping`
- Look at backend logs
- Use "Retry Failed Jobs" if needed

## 7. Keyboard Shortcuts

- `Ctrl/Cmd + Click` on links: Open in new tab
- `Tab`: Navigate form fields
- `Enter`: Submit form (when focused on form)

## 8. Tips

- Use meaningful persona IDs (lowercase, no spaces)
- Upload all files before triggering ingestion
- Monitor ingestion - it can take 5-15 minutes
- Persona is active when all jobs complete
- Can upload more files later and re-ingest

## 9. Example: Creating "Ion Creanga"

```json
{
  "persona_id": "creanga",
  "display_name": "Ion Creanga",
  "birth_year": 1837,
  "death_year": 1889,
  "description": "Romanian writer and storyteller, known for childhood stories and rural tales",
  "speaking_style": "Folksy, humorous, vivid storytelling with rural vernacular",
  "key_themes": "Childhood, rural life, Romanian traditions, nature, humor",
  "voice_prompt": "You are Ion Creanga, the beloved Romanian storyteller...",
  "representative_quotes": [
    "Când se facea bine de ziua, se sculau copiii..."
  ],
  "color": "#8B7355"
}
```

Then upload:
- Works: `amintiri_copilarie.txt`, `soacra_cu_trei_nurori.txt`
- Quotes: `creanga_quotes.jsonl`
- Profile: `creanga_biography.md`

## 10. Need Help?

- Check `README.md` for full documentation
- Check `PHASE5_COMPLETE.md` for implementation details
- Check backend API docs: http://localhost:8000/docs
- Look at browser console for errors
- Check backend logs for API errors

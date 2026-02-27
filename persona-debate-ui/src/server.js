const express = require('express');
const axios = require('axios');
const cors = require('cors');
const path = require('path');
const basicAuth = require('express-basic-auth');

const app = express();
const PORT = process.env.PORT || 3000;

// MCP server configuration
const MCP_SERVER_URL = process.env.MCP_SERVER_URL || 'http://3.83.102.160:8080';

// Tavily API key (optional - for web search)
const TAVILY_API_KEY = process.env.TAVILY_API_KEY;

// Password protection (optional - set ACCESS_PASSWORD env var to enable)
const ACCESS_PASSWORD = process.env.ACCESS_PASSWORD;

app.use(cors());
app.use(express.json());

// Basic auth middleware (only if ACCESS_PASSWORD is set)
if (ACCESS_PASSWORD) {
  console.log('🔒 Password protection ENABLED');
  app.use(basicAuth({
    users: { 'admin': ACCESS_PASSWORD },
    challenge: true,
    realm: 'Romanian Personas Debate',
    unauthorizedResponse: (req) => {
      return 'Acces restricționat. Introduceți parola pentru a continua.';
    }
  }));
} else {
  console.log('🔓 Password protection DISABLED (set ACCESS_PASSWORD to enable)');
}

app.use(express.static('public'));

// FastAPI backend URL
const FASTAPI_URL = process.env.FASTAPI_URL || 'http://localhost:8000';

// Hardcoded persona fallback (for backward compatibility)
const HARDCODED_PERSONAS = {
  eminescu: {
    name: 'Mihai Eminescu',
    title: 'Poetul național (1850-1889)',
    color: '#8b4513'
  },
  caragiale: {
    name: 'Ion Luca Caragiale',
    title: 'Dramaturg și satirist (1852-1912)',
    color: '#2e7d32'
  },
  bratianu: {
    name: 'Ion C. Brătianu',
    title: 'Om de stat (1821-1891)',
    color: '#1565c0'
  },
  eliade: {
    name: 'Mircea Eliade',
    title: 'Istoric al religiilor (1907-1986)',
    color: '#6a1b9a'
  },
  cioran: {
    name: 'Emil Cioran',
    title: 'Filosof și eseist (1911-1995)',
    color: '#c62828'
  }
};

// Persona cache with 30s TTL
let PERSONAS_CACHE = null;
let CACHE_TIMESTAMP = 0;
const CACHE_TTL = 30000; // 30 seconds

// Fetch personas from FastAPI backend
async function getPersonas() {
  const now = Date.now();

  // Return cached data if still valid
  if (PERSONAS_CACHE && (now - CACHE_TIMESTAMP) < CACHE_TTL) {
    return PERSONAS_CACHE;
  }

  try {
    console.log('Fetching personas from FastAPI backend...');
    const response = await axios.get(`${FASTAPI_URL}/api/personas`, {
      timeout: 5000
    });

    const dbPersonas = response.data.personas;

    // Transform API response to legacy format
    const personas = {};
    for (const p of dbPersonas) {
      personas[p.persona_id] = {
        name: p.display_name,
        title: `${p.birth_year}-${p.death_year || 'prezent'}`,
        color: p.color
      };
    }

    PERSONAS_CACHE = personas;
    CACHE_TIMESTAMP = now;
    console.log(`✓ Loaded ${Object.keys(personas).length} personas from API`);
    return personas;
  } catch (error) {
    console.error('Failed to fetch personas from API:', error.message);
    console.log('Falling back to hardcoded personas');
    return HARDCODED_PERSONAS;
  }
}

// Search the web for context about the question using Tavily API
async function searchWebContext(question) {
  if (!TAVILY_API_KEY) {
    console.log('Tavily API key not set, skipping web search');
    return null;
  }

  try {
    console.log(`Searching web for context: "${question.substring(0, 100)}..."`);

    const response = await axios.post('https://api.tavily.com/search', {
      api_key: TAVILY_API_KEY,
      query: question,
      search_depth: 'basic',
      max_results: 3,
      include_answer: true,
      include_raw_content: false
    }, {
      timeout: 10000,
      headers: { 'Content-Type': 'application/json' }
    });

    const data = response.data;

    if (data && data.answer) {
      console.log(`✓ Web search completed (${data.results?.length || 0} results)`);

      // Build context summary
      let context = `CONTEXT WEB (pentru informare):\n\n`;
      context += `${data.answer}\n\n`;

      if (data.results && data.results.length > 0) {
        context += `Surse:\n`;
        data.results.forEach((result, idx) => {
          context += `${idx + 1}. ${result.title} - ${result.url}\n`;
        });
      }

      return context;
    }

    return null;
  } catch (error) {
    console.error('Web search error:', error.message);
    return null;
  }
}

// Call MCP server ask_persona tool
async function askPersona(persona, query) {
  try {
    const response = await axios.post(
      `${MCP_SERVER_URL}/mcp`,
      {
        jsonrpc: '2.0',
        id: Date.now(),
        method: 'tools/call',
        params: {
          name: 'ask_persona',
          arguments: {
            query: query,
            persona: persona
          }
        }
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json, text/event-stream'
        },
        timeout: 120000 // 2 minute timeout
      }
    );

    // Parse SSE response
    const data = response.data;
    if (typeof data === 'string') {
      // Parse SSE format
      const lines = data.split('\n');
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonData = JSON.parse(line.substring(6));
          if (jsonData.result && jsonData.result.content) {
            const content = jsonData.result.content.find(c => c.type === 'text');
            return content ? content.text : 'No response';
          }
        }
      }
    } else if (data.result && data.result.content) {
      const content = data.result.content.find(c => c.type === 'text');
      return content ? content.text : 'No response';
    }

    return 'No response received';
  } catch (error) {
    console.error(`Error calling persona ${persona}:`, error.message);
    throw new Error(`Failed to get response from ${persona}: ${error.message}`);
  }
}

// API endpoint to get personas
app.get('/api/personas', async (req, res) => {
  try {
    const personas = await getPersonas();
    res.json(personas);
  } catch (error) {
    console.error('Error fetching personas:', error);
    res.status(500).json({ error: 'Failed to fetch personas' });
  }
});

// API endpoint for debate with streaming
app.post('/api/debate', async (req, res) => {
  const { question, personas, previousRounds = [] } = req.body;

  if (!question || !personas || personas.length === 0) {
    return res.status(400).json({ error: 'Question and personas are required' });
  }

  // Validate personas against current list
  const validPersonas = await getPersonas();
  const invalidPersonas = personas.filter(p => !validPersonas[p]);
  if (invalidPersonas.length > 0) {
    return res.status(400).json({
      error: `Invalid persona IDs: ${invalidPersonas.join(', ')}`
    });
  }

  // Set up SSE headers
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  try {
    const roundResults = [];
    const PERSONAS = validPersonas; // Use dynamically fetched personas

    // Build context from previous rounds (with truncation to avoid context overflow)
    let contextPrefix = '';
    if (previousRounds.length > 0) {
      contextPrefix = 'CONVERSAȚIA ANTERIOARĂ:\n\n';
      previousRounds.forEach((round, idx) => {
        contextPrefix += `=== RUNDA ${idx + 1} ===\n`;
        contextPrefix += `Întrebare: ${round.question}\n\n`;
        round.responses.forEach(resp => {
          // Truncate previous round responses to 600 chars to save context
          const truncated = resp.response.length > 600
            ? resp.response.substring(0, 600) + '...[rezumat]'
            : resp.response;
          contextPrefix += `${PERSONAS[resp.persona].name}: ${truncated}\n\n`;
        });
      });
      contextPrefix += '=== RUNDA ACTUALĂ ===\n\n';
    }

    // Search web for context (only for first round)
    let webContext = '';
    if (previousRounds.length === 0 && TAVILY_API_KEY) {
      res.write(`data: ${JSON.stringify({ type: 'searching', message: 'Căutare informații pe web...' })}\n\n`);
      webContext = await searchWebContext(question);
      if (webContext) {
        contextPrefix = webContext + '\n' + contextPrefix;
        res.write(`data: ${JSON.stringify({ type: 'search_complete', message: 'Context web găsit ✓' })}\n\n`);
      }
    }

    // Send initial status
    res.write(`data: ${JSON.stringify({ type: 'start', question, personaCount: personas.length })}\n\n`);

    // Call each persona in order
    for (let i = 0; i < personas.length; i++) {
      const persona = personas[i];

      // Send "thinking" status
      res.write(`data: ${JSON.stringify({ type: 'thinking', persona, index: i })}\n\n`);

      // Build query with context from this round's previous responses
      let fullQuery = contextPrefix;

      if (i === 0) {
        // First persona in this round gets the original question
        fullQuery += `Întrebare: ${question}`;
      } else {
        // Subsequent personas see previous responses in this round
        fullQuery += `Întrebare: ${question}\n\n`;
        fullQuery += `Răspunsuri anterioare în această rundă:\n\n`;
        for (let j = 0; j < i; j++) {
          const prevPersona = personas[j];
          const prevResponse = roundResults[j];

          // Truncate long responses to avoid context overflow
          // Keep first 800 chars for earlier personas, 1200 for immediate predecessor
          const maxLength = (j === i - 1) ? 1200 : 800;
          const truncated = prevResponse.response.length > maxLength
            ? prevResponse.response.substring(0, maxLength) + '...[rezumat]'
            : prevResponse.response;

          fullQuery += `${PERSONAS[prevPersona].name}: ${truncated}\n\n`;
        }
        fullQuery += `Acum răspunde tu, ${PERSONAS[persona].name}, ținând cont de cele spuse anterior.`;
      }

      console.log(`Calling ${persona}...`);
      const response = await askPersona(persona, fullQuery);

      const result = {
        persona: persona,
        response: response,
        timestamp: new Date().toISOString()
      };

      roundResults.push(result);

      // Stream the response immediately
      res.write(`data: ${JSON.stringify({ type: 'response', ...result, index: i })}\n\n`);

      console.log(`✓ ${persona} responded (${response.length} chars)`);
    }

    // Send completion
    res.write(`data: ${JSON.stringify({ type: 'complete', question, responses: roundResults })}\n\n`);
    res.end();

  } catch (error) {
    console.error('Debate error:', error);
    res.write(`data: ${JSON.stringify({ type: 'error', message: error.message })}\n\n`);
    res.end();
  }
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', mcpServer: MCP_SERVER_URL });
});

// Serve index.html for all other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../public/index.html'));
});

app.listen(PORT, () => {
  console.log(`Persona Debate UI running on http://localhost:${PORT}`);
  console.log(`MCP Server: ${MCP_SERVER_URL}`);
});

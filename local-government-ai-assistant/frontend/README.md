# RAG Chat UI

Simple single-page chat interface for Vietnamese government document RAG system.

## Quick Start

1. Start backend:
   ```bash
   cd ../backend
   python -m app.main
   ```

2. Open frontend:
   ```bash
   cd frontend
   # Option 1: Python simple server
   python -m http.server 3000
   
   # Option 2: Open directly in browser
   open index.html
   ```

3. Access: http://localhost:3000

## Features

- ✅ Clean chat interface
- ✅ Call backend API
- ✅ Display answers with sources
- ✅ Loading indicator
- ✅ Error handling
- ✅ Mobile responsive
- ✅ Vietnamese support

## API Configuration

Backend URL is configured in `script.js`:
```javascript
const API_BASE_URL = 'http://localhost:8000/api/v1';
```

Change this if backend runs on different port.

## Browser Compatibility

- Chrome/Edge: ✅
- Firefox: ✅
- Safari: ✅
- Mobile browsers: ✅

No build tools required - just open `index.html`!

## Testing

```bash
# 1. Start backend
cd backend
python -m app.main

# 2. Open frontend
cd ../frontend
python -m http.server 3000
# Open http://localhost:3000

# 3. Test queries:
- "Điều 10 quy định gì về hộ khẩu?"
- "Thủ tục làm CMND cần giấy tờ gì?"
```

## File Structure

```
frontend/
├── index.html    # Main HTML structure
├── style.css     # Styling and responsive design
├── script.js     # API integration and UI logic
└── README.md     # This file
```

## Customization

### Change Backend URL

Edit `script.js`:
```javascript
const API_BASE_URL = 'http://your-server:port/api/v1';
```

### Modify Colors

Edit `style.css`:
```css
/* Primary color */
background: #2563eb;  /* Change to your color */

/* User message bubble */
.user-message .message-content {
    background: #your-color;
}
```

### Adjust Layout

Edit `style.css`:
```css
.container {
    max-width: 800px;  /* Change max width */
}
```

## Troubleshooting

### CORS Error
If you see CORS errors in browser console, ensure backend has CORS enabled:
```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific origin
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Connection Refused
- Check backend is running on port 8000
- Check `API_BASE_URL` in `script.js` matches backend port

### Vietnamese Characters Not Displaying
- Ensure files are saved with UTF-8 encoding
- Check browser encoding is set to UTF-8

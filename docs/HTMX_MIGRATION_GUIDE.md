# HTMX Migration Guide
## Converting from JSON API to HTMX HTML Responses

**Current State:** Your app uses FastAPI with JSONResponse (traditional REST API)
**Desired State:** Use FastAPI with HTMX (HTML fragments)
**Benefit:** Less JavaScript, cleaner code, faster development

---

## Why HTMX?

### Current Approach (JSON + JavaScript)
```python
# Backend returns JSON
return JSONResponse({'status': 'started', 'progress': 45})
```

```javascript
// Frontend needs JavaScript to update DOM
fetch('/api/status')
    .then(r => r.json())
    .then(data => {
        document.getElementById('status').innerHTML = `Progress: ${data.progress}%`;
    });
```

**Problems:**
- Need to write JavaScript for every interaction
- Duplicate logic (backend sends data, frontend renders it)
- More code to maintain

### HTMX Approach (HTML Fragments)
```python
# Backend returns HTML
return templates.TemplateResponse("partials/status.html",
    {"request": request, "progress": 45})
```

```html
<!-- Frontend: Zero JavaScript needed! -->
<div hx-get="/api/status"
     hx-trigger="every 2s"
     hx-swap="innerHTML">
    Progress: 45%
</div>
```

**Benefits:**
- No JavaScript needed for most interactions
- Server renders HTML once (no duplication)
- Faster development

---

## Step-by-Step Conversion

### Step 1: Create HTML Partials Directory

```bash
mkdir -p app/gui/templates/partials
```

### Step 2: Convert One Endpoint at a Time

Let's convert `/start-processing` as an example:

#### Before (JSON):
```python
# app/gui/routers/processing.py
@router.post("/start-processing")
async def start_processing(request: Request):
    # ... processing logic ...
    return JSONResponse({
        'success': True,
        'operation_id': operation_id,
        'message': 'Processing started'
    })
```

#### After (HTMX):

**1. Create the HTML partial:**
```html
<!-- app/gui/templates/partials/processing_started.html -->
<div class="alert alert-success" id="operation-{{ operation_id }}">
    <h3>✅ Processing Started</h3>
    <p>{{ message }}</p>
    <p class="text-muted">Operation ID: {{ operation_id }}</p>

    <!-- Progress bar that updates automatically -->
    <div hx-get="/api/progress/{{ operation_id }}"
         hx-trigger="every 1s"
         hx-swap="outerHTML">
        <div class="progress">
            <div class="progress-bar" style="width: 0%">0%</div>
        </div>
    </div>
</div>
```

**2. Update the Python endpoint:**
```python
# app/gui/routers/processing.py
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/gui/templates")

@router.post("/start-processing")
async def start_processing(request: Request):
    # ... processing logic ...

    # Return HTML instead of JSON
    return templates.TemplateResponse(
        "partials/processing_started.html",
        {
            "request": request,  # Required by Jinja2
            "operation_id": operation_id,
            "message": "Processing started successfully"
        }
    )
```

**3. Update the frontend HTML:**
```html
<!-- app/gui/templates/index.html -->
<!-- OLD: Button with JavaScript -->
<button onclick="startProcessing()">Start</button>
<div id="status"></div>

<script>
function startProcessing() {
    fetch('/start-processing', {method: 'POST'})
        .then(r => r.json())
        .then(data => {
            document.getElementById('status').innerHTML = data.message;
        });
}
</script>

<!-- NEW: Button with HTMX -->
<button hx-post="/start-processing"
        hx-target="#status"
        hx-swap="innerHTML"
        hx-indicator="#loading">
    Start Processing
</button>

<div id="status"></div>
<div id="loading" class="htmx-indicator">Loading...</div>

<!-- No JavaScript needed! -->
```

---

## Common Patterns

### Pattern 1: Progress Updates

**JSON Approach:**
```python
@router.get("/progress/{operation_id}")
async def get_progress(operation_id: str):
    operation = get_operation(operation_id)
    return JSONResponse({
        'progress': operation.progress,
        'current_file': operation.current_file,
        'status': operation.status
    })
```

```javascript
setInterval(() => {
    fetch(`/progress/${operationId}`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('progress').innerHTML =
                `${data.progress}% - ${data.current_file}`;
        });
}, 1000);
```

**HTMX Approach:**
```python
@router.get("/progress/{operation_id}")
async def get_progress(request: Request, operation_id: str):
    operation = get_operation(operation_id)
    return templates.TemplateResponse(
        "partials/progress_bar.html",
        {
            "request": request,
            "progress": operation.progress,
            "current_file": operation.current_file,
            "status": operation.status
        }
    )
```

```html
<!-- partials/progress_bar.html -->
<div class="progress-container"
     hx-get="/progress/{{ operation_id }}"
     hx-trigger="every 1s"
     hx-swap="outerHTML">

    <div class="progress-bar" style="width: {{ progress }}%">
        {{ progress }}%
    </div>
    <p class="current-file">{{ current_file }}</p>
    <span class="badge">{{ status }}</span>
</div>
```

---

### Pattern 2: Form Submission

**JSON Approach:**
```html
<form onsubmit="handleSubmit(event)">
    <input name="path" />
    <button type="submit">Submit</button>
</form>

<script>
async function handleSubmit(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const response = await fetch('/validate-path', {
        method: 'POST',
        body: formData
    });
    const data = await response.json();
    document.getElementById('result').innerHTML = data.message;
}
</script>
```

**HTMX Approach:**
```html
<form hx-post="/validate-path"
      hx-target="#result"
      hx-swap="innerHTML">
    <input name="path" />
    <button type="submit">Submit</button>
</form>

<div id="result"></div>
<!-- Zero JavaScript! -->
```

---

### Pattern 3: Conditional Rendering

**JSON Approach:**
```python
return JSONResponse({
    'success': True,
    'files': files
})
```

```javascript
if (data.success) {
    let html = '<ul>';
    data.files.forEach(f => {
        html += `<li>${f.name}</li>`;
    });
    html += '</ul>';
    document.getElementById('files').innerHTML = html;
}
```

**HTMX Approach:**
```python
return templates.TemplateResponse(
    "partials/file_list.html",
    {
        "request": request,
        "success": True,
        "files": files
    }
)
```

```html
<!-- partials/file_list.html -->
{% if success %}
    <ul class="file-list">
        {% for file in files %}
            <li>{{ file.name }}</li>
        {% endfor %}
    </ul>
{% else %}
    <div class="alert alert-error">No files found</div>
{% endif %}
```

---

## HTMX Attributes Reference

### Core Attributes

```html
<!-- Trigger HTTP requests -->
hx-get="/api/data"          <!-- GET request -->
hx-post="/api/submit"       <!-- POST request -->
hx-put="/api/update"        <!-- PUT request -->
hx-delete="/api/delete"     <!-- DELETE request -->

<!-- Control where response goes -->
hx-target="#result"         <!-- Swap into #result -->
hx-target="closest div"     <!-- Swap into closest div -->

<!-- Control how to swap -->
hx-swap="innerHTML"         <!-- Replace inside (default) -->
hx-swap="outerHTML"         <!-- Replace element itself -->
hx-swap="beforebegin"       <!-- Insert before element -->
hx-swap="afterend"          <!-- Insert after element -->

<!-- Control when to trigger -->
hx-trigger="click"          <!-- On click (default for buttons) -->
hx-trigger="change"         <!-- On change (inputs) -->
hx-trigger="every 2s"       <!-- Every 2 seconds -->
hx-trigger="load"           <!-- On page load -->

<!-- Loading indicators -->
hx-indicator="#loading"     <!-- Show #loading while request -->

<!-- Include extra data -->
hx-include="[name='token']" <!-- Include other inputs -->
```

---

## Migration Checklist

### Phase 1: Setup
- [ ] Create `app/gui/templates/partials/` directory
- [ ] Set up Jinja2Templates in routers
- [ ] Include HTMX in HTML (`<script src="https://unpkg.com/htmx.org@1.9.10"></script>`)

### Phase 2: Convert Endpoints (One at a Time)

#### Progress Router (`app/gui/routers/progress.py`)
- [ ] `/api/progress/{operation_id}` → Return HTML partial

#### Processing Router (`app/gui/routers/processing.py`)
- [ ] `/start-processing` → Return HTML partial
- [ ] `/cancel/{operation_id}` → Return HTML partial
- [ ] `/upload` → Return HTML partial
- [ ] `/extract` → Return HTML partial

#### Paths Router (`app/gui/routers/paths.py`)
- [ ] `/api/paths/detect` → Return HTML partial
- [ ] `/api/paths/validate` → Return HTML partial
- [ ] `/api/paths/complete` → Return HTML partial
- [ ] `/api/paths/resolve-directory` → Return HTML partial
- [ ] `/api/paths/create` → Return HTML partial
- [ ] `/api/paths/suggest-output` → Return HTML partial

#### System Router (`app/gui/routers/system.py`)
- [ ] `/api/system/open-folder` → Return HTML partial
- [ ] `/api/system/info` → Return HTML partial

#### Logs Router (`app/gui/routers/logs.py`)
- [ ] `/api/logs/{operation_id}` → Return HTML partial
- [ ] `/api/recovery-info` → Return HTML partial

### Phase 3: Update Frontend
- [ ] Replace `<script>` tags with HTMX attributes
- [ ] Remove fetch() calls
- [ ] Remove JSON parsing code
- [ ] Test all interactions

### Phase 4: Cleanup
- [ ] Delete unused JavaScript files
- [ ] Remove JSONResponse imports
- [ ] Update documentation

---

## Example: Full Conversion of Progress Router

### Before (JSON):
```python
# app/gui/routers/progress.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/api/progress/{operation_id}")
async def get_progress(operation_id: str):
    operation = gui_state.active_operations.get(operation_id)

    if not operation:
        return JSONResponse({
            'success': False,
            'error': 'Operation not found'
        }, status_code=404)

    return JSONResponse({
        'success': True,
        'operation': operation,
        'progress': operation.get('progress_percent', 0),
        'status': operation.get('status', 'unknown')
    })
```

### After (HTMX):
```python
# app/gui/routers/progress.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

@router.get("/api/progress/{operation_id}")
async def get_progress(request: Request, operation_id: str):
    operation = gui_state.active_operations.get(operation_id)

    if not operation:
        # Return error HTML instead of JSON
        return templates.TemplateResponse(
            "partials/error.html",
            {
                "request": request,
                "error": "Operation not found"
            },
            status_code=404
        )

    # Return progress HTML
    return templates.TemplateResponse(
        "partials/progress.html",
        {
            "request": request,
            "operation": operation,
            "progress": operation.get('progress_percent', 0),
            "status": operation.get('status', 'unknown'),
            "operation_id": operation_id
        }
    )
```

**HTML Partials:**

```html
<!-- app/gui/templates/partials/progress.html -->
<div class="progress-container"
     hx-get="/api/progress/{{ operation_id }}"
     hx-trigger="every 1s"
     hx-swap="outerHTML">

    <div class="progress-header">
        <h4>{{ operation.get('current_operation', 'Processing') }}</h4>
        <span class="badge badge-{{ status }}">{{ status }}</span>
    </div>

    <div class="progress">
        <div class="progress-bar"
             role="progressbar"
             style="width: {{ progress }}%"
             aria-valuenow="{{ progress }}"
             aria-valuemin="0"
             aria-valuemax="100">
            {{ progress|round(1) }}%
        </div>
    </div>

    <div class="progress-details">
        <p class="current-file">
            <strong>Current file:</strong>
            {{ operation.get('current_file', 'N/A') }}
        </p>

        <div class="stats">
            <span>Files: {{ operation.stats.get('copied_files', 0) }} / {{ operation.stats.get('total_files', 0) }}</span>
            <span>Errors: {{ operation.stats.get('errors', 0) }}</span>
        </div>
    </div>

    {% if status == 'processing' %}
        <button hx-post="/cancel/{{ operation_id }}"
                hx-target="closest .progress-container"
                class="btn btn-danger">
            Cancel
        </button>
    {% endif %}
</div>
```

```html
<!-- app/gui/templates/partials/error.html -->
<div class="alert alert-danger" role="alert">
    <h4>❌ Error</h4>
    <p>{{ error }}</p>
</div>
```

---

## Testing HTMX Responses

```bash
# Test that endpoint returns HTML (not JSON)
curl -H "HX-Request: true" http://localhost:8000/api/progress/123

# Should return HTML:
# <div class="progress-container">...</div>

# Not JSON:
# {"success": true, "progress": 45}
```

---

## Benefits After Migration

### Before (JSON + JavaScript)
- **Lines of JavaScript:** ~500+ lines
- **Endpoints:** Return JSON
- **Frontend complexity:** HIGH
- **Maintenance:** Duplicate logic

### After (HTMX)
- **Lines of JavaScript:** ~0-50 lines
- **Endpoints:** Return HTML
- **Frontend complexity:** LOW
- **Maintenance:** Single source of truth

---

## Hybrid Approach (Recommended for Migration)

You don't have to convert everything at once. You can support **both** JSON and HTML:

```python
@router.get("/api/progress/{operation_id}")
async def get_progress(request: Request, operation_id: str):
    operation = gui_state.active_operations.get(operation_id)

    # Check if request is from HTMX
    if "HX-Request" in request.headers:
        # Return HTML for HTMX
        return templates.TemplateResponse(
            "partials/progress.html",
            {"request": request, "operation": operation}
        )
    else:
        # Return JSON for backward compatibility
        return JSONResponse({
            'operation': operation,
            'progress': operation.get('progress_percent', 0)
        })
```

This lets you migrate gradually without breaking existing functionality.

---

## Common Gotchas

### 1. Always Pass `request` to Templates
```python
# ❌ Wrong - will error
return templates.TemplateResponse(
    "partial.html",
    {"operation": operation}
)

# ✅ Correct
return templates.TemplateResponse(
    "partial.html",
    {"request": request, "operation": operation}  # Include request!
)
```

### 2. HTMX Expects HTML, Not JSON
```python
# ❌ Wrong - HTMX can't use this
return JSONResponse({'message': 'Success'})

# ✅ Correct
return templates.TemplateResponse(
    "partials/success.html",
    {"request": request, "message": "Success"}
)
```

### 3. Remember to Import Templates
```python
from fastapi.templating import Jinja2Templates
from pathlib import Path

templates = Jinja2Templates(
    directory=Path(__file__).parent.parent / "templates"
)
```

---

## Next Steps

1. **Start Small:** Convert one endpoint (like `/api/progress`)
2. **Test Thoroughly:** Make sure HTML renders correctly
3. **Convert More:** Once comfortable, convert other endpoints
4. **Remove JSON:** Eventually deprecate JSON responses
5. **Delete JavaScript:** Remove unused fetch() code

---

## Resources

- [HTMX Documentation](https://htmx.org/)
- [HTMX Examples](https://htmx.org/examples/)
- [FastAPI Templates](https://fastapi.tiangolo.com/advanced/templates/)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)

---

**Ready to start?** Begin with Phase 1 (Setup) and convert one endpoint at a time!

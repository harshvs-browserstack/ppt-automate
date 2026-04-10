# GAS Logger Usage

The `Logger.gs` file provides logging functions for all GAS files. All logs are written to the Google Sheet at:
https://docs.google.com/spreadsheets/d/1xlt59GxHLeyNJMnoiRGM4nP-9sT7lfdZPVHKYmtrktA/edit?gid=0#gid=0

## Functions

```javascript
logInfo_(component, message, details)      // Info level
logWarning_(component, message, details)   // Warning level
logError_(component, message, details)     // Error level
logSuccess_(component, message, details)   // Success level
logDebug_(component, message, details)     // Debug level
```

## Usage Examples

### In TemplateGenerator.gs
```javascript
function mainGenerateTemplate() {
  logInfo_("TemplateGenerator", "Starting template generation", `Master ID: ${ORIGINAL_SLIDES_ID}`);
  
  try {
    // ... your code ...
    logSuccess_("TemplateGenerator", "Template created", `Template ID: ${TEMPLATE_ID}`);
  } catch (e) {
    logError_("TemplateGenerator", "Template generation failed", e.message);
    throw e;
  }
}
```

### In Populate.gs
```javascript
function populateTemplateFromSheet() {
  logInfo_("Populate", "Starting population", `Content Sheet: ${CONTENT_SHEET_ID}`);
  
  try {
    // ... your code ...
    logSuccess_("Populate", "Population complete", `URL: ${presentationUrl}`);
    return presentationUrl;
  } catch (e) {
    logError_("Populate", "Population failed", e.message);
    throw e;
  }
}
```

### In Main.gs
```javascript
function pptGeneratorMain(mode) {
  logInfo_("Main", `Running mode: ${mode}`, "");
  
  try {
    // ... your code ...
  } catch (e) {
    logError_("Main", `Failed in mode ${mode}`, e.message);
    throw e;
  }
}
```

## Log Columns

- **Timestamp**: ISO format timestamp
- **Level**: INFO, WARNING, ERROR, SUCCESS, DEBUG
- **Component**: Which GAS file is logging (TemplateGenerator, Populate, Main, WebApp)
- **Message**: Main message
- **Details**: Optional additional details (error stack, IDs, etc.)

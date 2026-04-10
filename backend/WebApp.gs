/**
 * FILE: WebApp.gs
 * Handles all GET and POST requests to the web app.
 */

/**
 * Handles all GET requests. Acts as a router.
 * ?action=getProperty&key=MY_KEY
 * ?action=run&mode=template
 * ?action=run&mode=slides
 * ?action=getStyleMap
 */
function doGet(e) {
  var action = e.parameter.action;

  if (!action) {
    return createJsonResponse_({ error: "No 'action' parameter provided." });
  }

  try {
    switch (action) {
      case 'getProperty':
        const key = e.parameter.key;
        if (!key) {
          return createJsonResponse_({ error: "No 'key' parameter provided for getProperty." });
        }
        const scriptProjectProperties = PropertiesService.getScriptProperties();
        const value = scriptProjectProperties.getProperty(key);
        return createJsonResponse_({ key: key, value: value });

      case 'setProperty':
        // Lock service is useful to prevent race conditions when writing properties
        var lock = LockService.getScriptLock();
        lock.waitLock(2000);
        try {
          var key_set = e.parameter.key;
          var value_set = e.parameter.value;

          if (!key_set || !value_set) {
            return ContentService.createTextOutput(JSON.stringify({"status": "error", "message": "Missing key or value"}))
              .setMimeType(ContentService.MimeType.JSON);
          }

          PropertiesService.getScriptProperties().setProperty(key_set, value_set);

          return ContentService.createTextOutput(JSON.stringify({"status": "success", "key": key_set, "value": value_set}))
            .setMimeType(ContentService.MimeType.JSON);

        } catch (err) {
          return ContentService.createTextOutput(JSON.stringify({"status": "error", "message": err.toString()}))
            .setMimeType(ContentService.MimeType.JSON);
        } finally {
          lock.releaseLock();
        }

      case 'run':
        const mode = e.parameter.mode;
        if (!mode) {
          return createJsonResponse_({ error: "No 'mode' parameter provided for run." });
        }

        // This calls the main router in Main.gs
        const result = pptGeneratorMain(mode);

        if (mode === 'slides' && result) {
          return createJsonResponse_({ status: "success", mode: "slides", url: result });
        } else {
          return createJsonResponse_({ status: "success", mode: "template", result: result });
        }

      case 'getStyleMap':
        const smId = PropertiesService.getScriptProperties().getProperty('STYLEMAP_FILE_ID');
        if (!smId || smId === '-') {
          return createJsonResponse_({ error: 'STYLEMAP_FILE_ID not set or cleared.' });
        }
        const smContent = DriveApp.getFileById(smId).getBlob().getDataAsString();
        return ContentService.createTextOutput(smContent).setMimeType(ContentService.MimeType.JSON);

      default:
        return createJsonResponse_({ error: "Invalid action specified." });
    }
  } catch (err) {
    Logger.log(`Error in doGet: ${err}`);
    return createJsonResponse_({ error: "An internal error occurred.", details: err.message });
  }
}

/**
 * Handles POST requests.
 * Supports two actions:
 *   - setProperty: {"key": "MY_KEY", "value": "MY_VALUE"}
 *   - setContent:  {"action": "setContent", "rows": [[header...], [row...], ...]}
 */
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const action = data.action;

    // --- setContent: write rows directly to the content sheet ---
    if (action === 'setContent') {
      const sheetId = PropertiesService.getScriptProperties().getProperty('CONTENT_SHEET_ID');
      if (!sheetId || sheetId === '-') {
        return createJsonResponse_({ error: 'CONTENT_SHEET_ID not set or cleared.' });
      }
      const rows = data.rows;
      if (!rows || rows.length === 0) {
        return createJsonResponse_({ error: 'No rows provided.' });
      }
      const sheet = SpreadsheetApp.openById(sheetId).getSheets()[0];
      sheet.clearContents();
      sheet.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
      return createJsonResponse_({ status: 'success', rowsWritten: rows.length });
    }

    // --- setProperty: legacy single key/value write ---
    const key = data.key;
    const value = data.value;
    if (!key || value === undefined) {
      return createJsonResponse_({ error: "Request body must include 'action', or 'key' and 'value'." });
    }
    PropertiesService.getScriptProperties().setProperty(key, value);
    return createJsonResponse_({ status: "success", key: key, value: value });

  } catch (err) {
    Logger.log(`Error in doPost: ${err}`);
    return createJsonResponse_({ error: "An internal error occurred.", details: err.message });
  }
}

/**
 * [HELPER] Creates a JSON response for the web app.
 */
function createJsonResponse_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

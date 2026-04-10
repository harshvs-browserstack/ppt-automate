/**
 * FILE: Logger.gs
 * Google Sheets logging for GAS operations.
 * Writes logs to a configured Google Sheet for monitoring and debugging.
 */

const LOGGER_SHEET_ID = "1xlt59GxHLeyNJMnoiRGM4nP-9sT7lfdZPVHKYmtrktA";
const LOGGER_SHEET_NAME = "Logs";

/**
 * Append a log entry to the Google Sheet.
 * @param {string} level - Log level (INFO, WARNING, ERROR, SUCCESS, DEBUG)
 * @param {string} component - Component name (e.g., "TemplateGenerator", "Populate")
 * @param {string} message - Main log message
 * @param {string} details - Optional additional details
 */
function logToSheet_(level, component, message, details = "") {
  try {
    const timestamp = new Date().toISOString();
    const sheet = SpreadsheetApp.openById(LOGGER_SHEET_ID).getSheetByName(LOGGER_SHEET_NAME);

    // Ensure headers exist
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["Timestamp", "Level", "Component", "Message", "Details"]);
    }

    // Append log row
    sheet.appendRow([timestamp, level, component, message, details]);

    // Log to browser console as well
    Logger.log(`[${level}] ${component}: ${message}`);
  } catch (e) {
    Logger.log(`Warning: Could not write to logger sheet: ${e.message}`);
  }
}

/**
 * Log an info message.
 * @param {string} component
 * @param {string} message
 * @param {string} details
 */
function logInfo_(component, message, details = "") {
  logToSheet_("INFO", component, message, details);
}

/**
 * Log an error message.
 * @param {string} component
 * @param {string} message
 * @param {string} details
 */
function logError_(component, message, details = "") {
  logToSheet_("ERROR", component, message, details);
}

/**
 * Log a warning message.
 * @param {string} component
 * @param {string} message
 * @param {string} details
 */
function logWarning_(component, message, details = "") {
  logToSheet_("WARNING", component, message, details);
}

/**
 * Log a success message.
 * @param {string} component
 * @param {string} message
 * @param {string} details
 */
function logSuccess_(component, message, details = "") {
  logToSheet_("SUCCESS", component, message, details);
}

/**
 * Log a debug message.
 * @param {string} component
 * @param {string} message
 * @param {string} details
 */
function logDebug_(component, message, details = "") {
  logToSheet_("DEBUG", component, message, details);
}

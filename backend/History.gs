/**
 * FILE: History.gs
 * Logs all slide generations to a history sheet for audit trail.
 */

/**
 * Log a generation to the history sheet.
 * @param {string} slideUrl - The URL of the generated slide
 * @param {string} templateName - Name of the template used
 * @param {string} targetValue - The target variable value (e.g., competitor name)
 * @param {string} pdfFilename - Name of the uploaded PDF
 */
function logGeneration_(slideUrl, templateName, targetValue, pdfFilename) {
  try {
    const historySheetId = PropertiesService.getScriptProperties().getProperty('HISTORY_SHEET_ID');

    // If no history sheet configured, skip logging
    if (!historySheetId || historySheetId === '-') {
      Logger.log('History sheet not configured, skipping generation log.');
      return;
    }

    const spreadsheet = SpreadsheetApp.openById(historySheetId);
    let historySheet = spreadsheet.getSheetByName('Generations');

    // Create sheet if it doesn't exist
    if (!historySheet) {
      historySheet = spreadsheet.insertSheet('Generations');
      historySheet.appendRow([
        'Timestamp',
        'Template',
        'Target Value',
        'PDF Filename',
        'Slide URL',
        'Slide ID'
      ]);
    }

    // Extract slide ID from URL
    const slideIdMatch = slideUrl.match(/\/d\/([a-zA-Z0-9-_]+)/);
    const slideId = slideIdMatch ? slideIdMatch[1] : '';

    // Append generation record
    historySheet.appendRow([
      new Date().toISOString(),
      templateName || 'N/A',
      targetValue || 'N/A',
      pdfFilename || 'N/A',
      slideUrl,
      slideId
    ]);

    Logger.log(`Generation logged: ${slideId}`);
  } catch (e) {
    Logger.log(`Warning: Could not log generation to history: ${e.message}`);
  }
}

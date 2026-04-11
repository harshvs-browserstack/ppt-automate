/**
 * MAIN FUNCTION: Populates a Slides template with content from a Google Sheet.
 */
function populateTemplateFromSheet() {
  if (!CONTENT_SHEET_ID || !STYLEMAP_FILE_ID || !TEMPLATE_ID) {
    throw new Error(`Missing IDs. T: ${TEMPLATE_ID}, S: ${STYLEMAP_FILE_ID}, C: ${CONTENT_SHEET_ID}`);
  }

  const contentData = getContentFromSheet_();
  const styleMap = getJsonFromDrive_(STYLEMAP_FILE_ID);

  if (!contentData || Object.keys(contentData).length === 0) {
    Logger.log('No content to populate. Check your Google Sheet.');
    return "Error: No content found.";
  }

  const templateFile = DriveApp.getFileById(TEMPLATE_ID);
  const newPresentationFile = templateFile.makeCopy(`[POPULATED] ${templateFile.getName()}`);
  const newPresentation = SlidesApp.openById(newPresentationFile.getId());
  
  // [FIX] Capture URL
  const presentationUrl = newPresentationFile.getUrl();
  Logger.log(`Created new presentation: ${presentationUrl}`);

  styleMap.forEach(styleInfo => {
    if (contentData.hasOwnProperty(styleInfo.placeholderId)) {
      const contentItem = contentData[styleInfo.placeholderId];
      const newContentForTable = contentItem.newContent || ''; 
      
      let contentRuns = [];
      try {
        contentRuns = JSON.parse(contentItem.contentRuns || '[]');
      } catch (e) {
        Logger.log(`Warning: Could not parse contentRuns for ${styleInfo.placeholderId}. Error: ${e.message}`);
      }

      const element = newPresentation.getPageElementById(styleInfo.objectId);
      
      if (!element) {
        Logger.log(`Warning: Could not find element with ID: ${styleInfo.objectId} in template.`);
        return;
      }

      if (styleInfo.type === 'shape') {
        populateShape_(element.asShape(), contentRuns); // We only need contentRuns now
      } else if (styleInfo.type === 'table') {
        populateTable_(element.asTable(), newContentForTable);
      }
    }
  });

  newPresentation.saveAndClose();
  Logger.log('Population complete.');

  // Share with shared drive
  const sharedDriveId = PropertiesService.getScriptProperties().getProperty('GOOGLE_SHARED_DRIVE_ID');
  if (sharedDriveId && sharedDriveId !== '-') {
    try {
      shareSlideWithSharedDrive_(newPresentationFile.getId(), sharedDriveId);
      Logger.log('Slide shared with shared drive.');
    } catch (e) {
      Logger.log(`Warning: Could not share slide with shared drive: ${e.message}`);
    }
  }

  // Note: History logging is now handled by Python backend for complete data capture
  return presentationUrl;
}


// --- HELPER FUNCTIONS ---


function getContentFromSheet_() {
  const sheet = SpreadsheetApp.openById(CONTENT_SHEET_ID).getSheets()[0];
  const data = sheet.getDataRange().getValues();
  const headers = data.shift();

  const placeholderCol = headers.indexOf('placeholderId');
  const newContentCol = headers.indexOf('newContent');
  const contentRunsCol = headers.indexOf('contentRuns');

  if (placeholderCol === -1 || newContentCol === -1 || contentRunsCol === -1) {
    throw new Error("Could not find 'placeholderId', 'newContent', or 'contentRuns' columns in the sheet.");
  }

  const contentMap = {};
  data.forEach(row => {
    const placeholder = row[placeholderCol];
    if (placeholder) {
      contentMap[placeholder] = {
        newContent: row[newContentCol],
        contentRuns: row[contentRunsCol]
      };
    }
  });
  return contentMap;
}

/**
 * Populates a shape by iterating through each style run.
 */
function populateShape_(shape, contentRuns) {
  const textRange = shape.getText();
  textRange.clear();

  if (!contentRuns || !Array.isArray(contentRuns) || contentRuns.length === 0) {
    Logger.log(`No contentRuns for shape ${shape.getObjectId()}; leaving it empty.`);
    return;
  }

  contentRuns.forEach(run => {
    if (!run || typeof run.text !== 'string') return; 

    const segmentText = run.text;
    const appendedRange = textRange.appendText(segmentText);

    // [FIX] Logic updated to allow spaces to retain formatting 
    // (prevents breaking flow between words)
    if (segmentText.length > 0 && run.style) {
      const style = run.style;
      const textStyle = appendedRange.getTextStyle();
      
      if (style.bold !== undefined) textStyle.setBold(style.bold);
      if (style.italic !== undefined) textStyle.setItalic(style.italic);
      if (style.underline !== undefined) textStyle.setUnderline(style.underline);
      if (style.strikethrough !== undefined) textStyle.setStrikethrough(style.strikethrough);
      if (style.fontFamily) textStyle.setFontFamily(style.fontFamily);
      if (style.fontSize) textStyle.setFontSize(style.fontSize);
      applyForegroundColor_(textStyle, style.foregroundColor);
    }
  });
  Logger.log(`Populated shape ${shape.getObjectId()} with styled runs.`);
}


function applyForegroundColor_(textStyle, colorValue) {
  if (!colorValue) return;

  const THEME_COLOR_MAP = {
    "ACCENT1": SlidesApp.ThemeColorType.ACCENT1, "ACCENT2": SlidesApp.ThemeColorType.ACCENT2,
    "ACCENT3": SlidesApp.ThemeColorType.ACCENT3, "ACCENT4": SlidesApp.ThemeColorType.ACCENT4,
    "ACCENT5": SlidesApp.ThemeColorType.ACCENT5, "ACCENT6": SlidesApp.ThemeColorType.ACCENT6,
    "DARK1": SlidesApp.ThemeColorType.DARK1, "DARK2": SlidesApp.ThemeColorType.DARK2,
    "LIGHT1": SlidesApp.ThemeColorType.LIGHT1, "LIGHT2": SlidesApp.ThemeColorType.LIGHT2,
    "FOLLOWED_HYPERLINK": SlidesApp.ThemeColorType.FOLLOWED_HYPERLINK,
    "HYPERLINK": SlidesApp.ThemeColorType.HYPERLINK, "TEXT1": SlidesApp.ThemeColorType.TEXT1
  };

  try {
    if (colorValue.startsWith('#')) {
      textStyle.setForegroundColor(colorValue);
    } else if (THEME_COLOR_MAP[colorValue]) {
      textStyle.setForegroundColor(THEME_COLOR_MAP[colorValue]);
    } else {
      Logger.log(`Warning: Unrecognized color value "${colorValue}".`);
    }
  } catch (e) {
    Logger.log(`Error applying color "${colorValue}": ${e.message}`);
  }
}

function populateTable_(table, jsonString) {
  try {
    if (!jsonString) {
      for (let r = 0; r < table.getNumRows(); r++) {
        for (let c = 0; c < table.getNumColumns(); c++) {
          table.getCell(r, c).getText().setText('');
        }
      }
      Logger.log(`Cleared table ${table.getObjectId()}`);
      return;
    }

    const data = JSON.parse(jsonString);
    if (!Array.isArray(data)) throw new Error("Parsed JSON for table is not an array.");

    for (let r = 0; r < data.length; r++) {
      if (!Array.isArray(data[r])) continue;
      for (let c = 0; c < data[r].length; c++) {
        if (r < table.getNumRows() && c < table.getNumColumns()) {
          table.getCell(r, c).getText().setText(String(data[r][c]));
        }
      }
    }
    Logger.log(`Populated table ${table.getObjectId()}`);
  } catch (e) {
    Logger.log(`Could not populate table ${table.getObjectId()}. Invalid JSON. Error: ${e.message}`);
  }
}

function getJsonFromDrive_(fileId) {
  const file = DriveApp.getFileById(fileId);
  const jsonString = file.getBlob().getDataAsString();
  return JSON.parse(jsonString);
}

function shareSlideWithSharedDrive_(slideFileId, sharedDriveId) {
  try {
    const slideFile = DriveApp.getFileById(slideFileId);
    const sharedDrive = DriveApp.getFolderById(sharedDriveId);

    // Add the file to the shared drive
    sharedDrive.addFile(slideFile);
    Logger.log(`File ${slideFileId} moved to shared drive ${sharedDriveId}`);
  } catch (e) {
    Logger.log(`Error sharing slide: ${e.message}`);
    throw e;
  }
}
// Heuristics for Markdown/JSON export:
const HEADING_L2_MIN = 30; // pt
const HEADING_L3_MIN = 12; // pt
const CODE_FONTS = ['Consolas', 'Courier New', 'Roboto Mono', 'Fira Code', 'Source Code Pro'];
let stylingMode = false;

// [FIX] Declare these to prevent ReferenceErrors
let MARKDOWN_FILE_ID = null;
let STYLEMAP_FILE_ADDRESS = null;

/**
 * MAIN ENTRY: Creates template file, exports style map JSON, markdown export, and content sheet.
 * Run this function for the complete workflow.
 */
function mainGenerateTemplate() {
  // 1. Create content map (no styling)
  stylingMode = false;
  createTemplateAndExportStyleMap();  

  // 2. Create style map (with styling - used for Sheet)
  stylingMode = true;
  TEMPLATE_ID = createTemplateAndExportStyleMap();  
  
  // 3. Create content sheet
  createContentSheetFromStyleMap();

  // 4. Save Properties
  scriptProperties.setProperty('TEMPLATE_ID', TEMPLATE_ID);
  scriptProperties.setProperty('STYLEMAP_FILE_ID', STYLEMAP_FILE_ID);
  
  if (CONTENT_SHEET_ID) {
    scriptProperties.setProperty('CONTENT_SHEET_ID', CONTENT_SHEET_ID);
    userProperties.setProperty('CONTENT_SHEET_ID', CONTENT_SHEET_ID);
  }
  
  if (STYLEMAP_FILE_ADDRESS) {
    scriptProperties.setProperty('STYLEMAP_FILE_ADDRESS', STYLEMAP_FILE_ADDRESS);
    userProperties.setProperty('STYLEMAP_FILE_ADDRESS', STYLEMAP_FILE_ADDRESS);
  }
  
  if (MARKDOWN_FILE_ID) {
    scriptProperties.setProperty('MARKDOWN_FILE_ID', MARKDOWN_FILE_ID);
  }

  const saEmail = scriptProperties.getProperty('SERVICE_ACCOUNT_EMAIL');
  if (saEmail) {                                                                             
    DriveApp.getFileById(STYLEMAP_FILE_ID).addEditor(saEmail);
    SpreadsheetApp.openById(CONTENT_SHEET_ID).addEditor(saEmail);                            
  } 
  
  Logger.log('--- Workflow Complete ---');
  Logger.log(`Template ID: ${TEMPLATE_ID}`);
  Logger.log(`StyleMap JSON ID: ${STYLEMAP_FILE_ID}`);
  Logger.log(`Content Sheet ID: ${CONTENT_SHEET_ID}`);
  Logger.log(`StyleMap JSON Location: ${STYLEMAP_FILE_ADDRESS}`);
}

/**
 * 1. Copies the master Slides file as a template, scans it for a style map,
 * exports the map as JSON to Drive, and inserts placeholders into the template.
 * @returns {string} The ID of the newly created template file.
 */
function createTemplateAndExportStyleMap() {
  const master = SlidesApp.openById(ORIGINAL_SLIDES_ID);
  const masterFile = DriveApp.getFileById(master.getId());
  const templateFile = masterFile.makeCopy(`[TEMPLATE] ${master.getName()}`);
  const templateId = templateFile.getId();

  // Build the detailed style map from the master presentation
  const styleMap = buildStyleMapFromPresentation(master);

  const baseName = master.getName().replace(/[^\w\- ]/g, "");

  // Export the style map as a JSON file to Google Drive
  if(!stylingMode){
    STYLEMAP_FILE_ID = createFileInDrive(
      JSON.stringify(styleMap, null, 2),
      `${baseName}_ContentMap.json`
    );
  }
  else{
    const fileName = `${baseName}_StyleMap.json`;
    STYLEMAP_FILE_ID = createFileInDrive(
      JSON.stringify(styleMap, null, 2),
      fileName
    );
    STYLEMAP_FILE_ADDRESS = fileName;
  } 

  // Insert placeholders into the new template file
  const templatePres = SlidesApp.openById(templateId);
  applyPlaceholdersToTemplate(templatePres, styleMap);
  templatePres.saveAndClose();

  Logger.log(`Template copy ID: ${templateId}, Style map JSON ID: ${STYLEMAP_FILE_ID}`);
  return templateId;
}

/**
 * 2. Exports a markdown file and a content JSON file from the presentation.
 * @param {string} presentationId The ID of the presentation to export.
 */
function exportPresentationMarkdownAndJson(presentationId) {
  const pres = SlidesApp.openById(presentationId);
  const slidesData = extractSlidesToContentObject(pres);
  const baseName = pres.getName().replace(/[^\w\- ]/g, "");

  // Save both JSON and Markdown to Drive
  createFileInDrive(JSON.stringify(slidesData, null, 2), `${baseName}_Export.json`);
  MARKDOWN_FILE_ID = createFileInDrive(convertSlidesObjectToMarkdown(slidesData), `${baseName}.md`);
}

/**
 * 3. Generates a Google Sheet for content population based on the style map.
 */
function createContentSheetFromStyleMap() {
  const styleMap = getJsonFromDrive(STYLEMAP_FILE_ID);
  if (!styleMap || !styleMap.length) throw new Error("Style map JSON is missing or empty");

  const ss = SpreadsheetApp.create(`[CONTENT] ${DriveApp.getFileById(TEMPLATE_ID).getName()}`);
  CONTENT_SHEET_ID = ss.getId();
  const sheet = ss.getSheets()[0];
  const headers = ['placeholderId', 'slideNumber', 'type', 'originalContent', 'contentRuns', 'newContent'];
  
  const data = styleMap.map(e => [
    e.placeholderId,
    e.slideNumber,
    e.type,
    e.originalContent,
    JSON.stringify(e.contentRuns), // Stringify the array for the sheet
    ''
  ]);

  sheet.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
  if (data.length) sheet.getRange(2, 1, data.length, headers.length).setValues(data);
  for (let col = 1; col <= headers.length; ++col) sheet.autoResizeColumn(col);
  
  Logger.log(`Content sheet created: ${ss.getUrl()}`);
  DriveApp.getFileById(CONTENT_SHEET_ID).moveTo(DriveApp.getFolderById(FOLDER_DRIVE_ID));
}

// ---------- Core Logic Helpers ---------- //

function buildStyleMapFromPresentation(presentation) {
  const styleMap = [];
  presentation.getSlides().forEach((slide, slideIndex) => {
    slide.getPageElements().forEach(element => {
      const type = element.getPageElementType();
      let styleInfo = null;

      if (type === SlidesApp.PageElementType.SHAPE) {
        const shape = element.asShape();
        if (shape.getText().asString().trim() !== '') {
          styleInfo = analyzeShapeForStyleMap(shape, slideIndex + 1);
        }
      } else if (type === SlidesApp.PageElementType.TABLE) {
        styleInfo = analyzeTableForStyleMap(element.asTable(), slideIndex + 1);
      }

      if (styleInfo) {
        styleMap.push(styleInfo);
      }
    });
  });
  return styleMap;
}

function analyzeShapeForStyleMap(shape, slideNumber) {
  let placeholderType = 'body';
  try {
    const pType = shape.getPlaceholderType();
    if (pType === SlidesApp.PlaceholderType.TITLE || pType === SlidesApp.PlaceholderType.CENTERED_TITLE) {
      placeholderType = 'title';
    } else if (pType === SlidesApp.PlaceholderType.SUBTITLE) {
      placeholderType = 'subtitle';
    }
  } catch (e) { /* Not a placeholder shape, defaults to 'body' */ }

  if(!stylingMode){
    return {
      placeholderId: `{{shape_${shape.getObjectId()}}}`,
      objectId: shape.getObjectId(),
      slideNumber,
      type: 'shape',
      originalContent: shape.getText().asString()
    };
  }
  return {
    placeholderId: `{{shape_${shape.getObjectId()}}}`,
    objectId: shape.getObjectId(),
    slideNumber,
    type: 'shape',
    originalContent: shape.getText().asString().trim(),
    contentRuns: extractTextRuns(shape.getText())
  };
}

function analyzeTableForStyleMap(table, slideNumber) {
  const numRows = table.getNumRows();
  const numCols = table.getNumColumns();
  const tableData = [];
  for (let i = 0; i < numRows; i++) {
    const row = [];
    for (let j = 0; j < numCols; j++) {
      try {
        row.push(table.getCell(i, j).getText().asString().trim());
      } catch (e) {
        row.push("");
      }
    }
    tableData.push(row);
  }
  return {
    placeholderId: `{{table_${table.getObjectId()}}}`,
    objectId: table.getObjectId(),
    slideNumber,
    type: 'table',
    originalContent: JSON.stringify(tableData),
    contentRuns: [] 
  };
}

function extractTextRuns(textRange) {
  if (!textRange || !textRange.asString().trim()) return [];

  const runs = textRange.getRuns();

  return runs.map((run, index) => {
    const ts = run.getTextStyle();
    let colorValue = null;

    // Robustly get the foreground color.
    const fgColor = ts.getForegroundColor();
    if (fgColor) {
      const colorType = fgColor.getColorType();
      if (colorType === SlidesApp.ColorType.RGB) {
        colorValue = fgColor.asRgbColor().asHexString();
      } else if (colorType === SlidesApp.ColorType.THEME) {
        colorValue = fgColor.asThemeColor().getThemeColorType().toString();
      }
    }

    const style = {
      bold: ts.isBold(),
      italic: ts.isItalic(),
      underline: ts.isUnderline(),
      strikethrough: ts.isStrikethrough(),
      fontFamily: ts.getFontFamily(),
      fontSize: ts.getFontSize(),
      foregroundColor: colorValue
    };

    let runText = run.asString();
    if(index === runs.length - 1){
      runText = runText.replace(/\s+$/, '');
    }

    return {
      text: runText,
      style: style,
      linkUrl: ts.getLink() ? ts.getLink().getUrl() : null
    };
  });
}

function applyPlaceholdersToTemplate(presentation, styleMap) {
  styleMap.forEach(info => {
    const el = presentation.getPageElementById(info.objectId);
    if (!el) {
      Logger.log(`Warning: Could not find element with ID ${info.objectId} in template.`);
      return;
    }

    if (info.type === 'shape') {
      const txt = el.asShape().getText();
      txt.setText(info.placeholderId);
      txt.getRuns().forEach(run => {
        run.getTextStyle().setBold(false).setItalic(false).setUnderline(false);
      });
    } else if (info.type === 'table') {
      const table = el.asTable();
      for (let r = 0; r < table.getNumRows(); r++) {
        for (let c = 0; c < table.getNumColumns(); c++) {
          try { table.getCell(r, c).getText().setText(''); } catch (e) {}
        }
      }
      table.getCell(0, 0).getText().setText(info.placeholderId);
    }
  });
}

// ------------- Util ----------------- //

function createFileInDrive(content, filename) {
  const folder = DriveApp.getFolderById(FOLDER_DRIVE_ID);
  const file = folder.createFile(filename, content);
  Logger.log(`File created: ${file.getUrl()}`);
  return file.getId();
}

function getJsonFromDrive(fileId) {
  const file = DriveApp.getFileById(fileId);
  const jsonString = file.getBlob().getDataAsString();
  return JSON.parse(jsonString);
}

// Keep the rest of the existing Markdown export functions (extractSlidesToContentObject, etc.)
// ... (Your original markdown functions were fine, included here implicitly or you can paste them back) ...
function extractSlidesToContentObject(pres) {
  return pres.getSlides().map((slide, slideIndex) => {
    const elements = [];
    slide.getPageElements().forEach(element => {
      let item = null;
      const type = element.getPageElementType();
      if (type === SlidesApp.PageElementType.SHAPE) {
        item = structureShapeForExport(element.asShape());
      } else if (type === SlidesApp.PageElementType.IMAGE) {
        item = structureImageForExport(element.asImage());
      } else if (type === SlidesApp.PageElementType.TABLE) {
        item = structureTableForExport(element.asTable());
      }
      if (item) {
        item.top = element.getTop(); // vertical position for sorting
        elements.push(item);
      }
    });
    elements.sort((a, b) => a.top - b.top);
    elements.forEach(e => delete e.top);

    const notesShape = slide.getNotesPage().getSpeakerNotesShape();
    const speakerNotes = notesShape ? textRangeToMarkdown(notesShape.getText()) : "";
    return {
      slideNumber: slideIndex + 1,
      objectId: slide.getObjectId(),
      content: elements,
      speakerNotes
    };
  });
}

function structureShapeForExport(shape) {
  if (!shape.getText || shape.getText().asString().trim() === '') return null;
  const text = shape.getText();
  const textString = text.asString().trim();

  if (text.getListParagraphs && text.getListParagraphs().length > 0)
    return { type: 'list', items: text.getListParagraphs().map(p => textRangeToMarkdown(p.getRange())) };

  if (CODE_FONTS.includes(text.getTextStyle().getFontFamily()))
    return { type: 'code', language: '', content: textString };

  try {
    const pType = shape.getPlaceholderType();
    if (pType === SlidesApp.PlaceholderType.TITLE || pType === SlidesApp.PlaceholderType.CENTERED_TITLE)
      return { type: 'heading', level: 1, content: textRangeToMarkdown(text) };
    if (pType === SlidesApp.PlaceholderType.SUBTITLE)
      return { type: 'heading', level: 2, content: textRangeToMarkdown(text) };
  } catch (e) {}
  
  const fontSize = text.getTextStyle().getFontSize();
  if (fontSize >= HEADING_L2_MIN)
    return { type: 'heading', level: 2, content: textRangeToMarkdown(text) };
  if (fontSize >= HEADING_L3_MIN)
    return { type: 'heading', level: 3, content: textRangeToMarkdown(text) };

  return { type: 'paragraph', content: textRangeToMarkdown(text) };
}

function structureImageForExport(image) {
  return {
    type: 'image',
    sourceUrl: image.getSourceUrl(),
    altText: image.getTitle() || image.getDescription() || ''
  };
}

function structureTableForExport(table) {
  const numRows = table.getNumRows();
  const numCols = table.getNumColumns();
  const tableData = [];
  for (let i = 0; i < numRows; i++) {
    const row = [];
    for (let j = 0; j < numCols; j++) {
      try { row.push(textRangeToMarkdown(table.getCell(i, j).getText())); }
      catch { row.push(""); }
    }
    tableData.push(row);
  }
  return { type: 'table', data: tableData };
}

function textRangeToMarkdown(textRange) {
  if (!textRange || textRange.asString().trim() === '') return '';
  let out = '';
  textRange.getRuns().forEach(run => {
    const txt = run.asString();
    const link = run.getTextStyle().getLink();
    out += link ? `[${txt}](${link.getUrl()})` : txt;
  });
  return out.trim();
}

function convertSlidesObjectToMarkdown(presentationData) {
  let md = '';
  presentationData.forEach(slide => {
    md += '\n\n---\n\n';
    slide.content.forEach(el => {
      switch (el.type) {
        case 'heading': md += `${'#'.repeat(el.level)} ${el.content}\n\n`; break;
        case 'paragraph': md += `${el.content}\n\n`; break;
        case 'list': el.items.forEach(item => md += `* ${item}\n`); md += '\n'; break;
        case 'image': md += `![${el.altText}](${el.sourceUrl})\n\n`; break;
        case 'code': md += `\`\`\`\n${el.content}\n\`\`\`\n\n`; break;
        case 'table':
          if (el.data && el.data.length > 0) {
            const headers = el.data[0];
            const separator = headers.map(() => '---').join(' | ');
            md += `| ${headers.join(' | ')} |\n| ${separator} |\n`;
            for (let i = 1; i < el.data.length; i++) md += `| ${el.data[i].join(' | ')} |\n`;
            md += '\n';
          }
          break;
      }
    });
    if (slide.speakerNotes) md += `> **Notes:** ${slide.speakerNotes.replace(/\n/g, ' ')}\n`;
  });
  return md;
}
// ------- Configuration -------
// const FOLDER_DRIVE_ID = '1MEMG4Vn9vIx6c-benXkfQT2EkI85c40C'; // Your folder ID

// These IDs are populated at runtime to avoid caching old values:
const scriptProperties = PropertiesService.getScriptProperties();
const userProperties = PropertiesService.getUserProperties();

// Initialize as null
let TEMPLATE_ID = null;
let STYLEMAP_FILE_ID = null;
let CONTENT_SHEET_ID = null;
let ORIGINAL_SLIDES_ID = null;
let FOLDER_DRIVE_ID = null;

// The ID of your master presentation
// const ORIGINAL_SLIDES_ID = '1P0E15T--fLb9F9S_IGLyqerLULdWGE7VHPnwB6XaEo0';
// const ORIGINAL_SLIDES_ID = `1Tk3hh6KvoyroIVAn90TfGPiYylMgKhbLqu6iEBOtS8E`;

/**
 * Main router function called by doGet.
 */
function main(){
  pptGeneratorMain('slides');
}

function pptGeneratorMain(mode) {
  // [FIX] Fetch properties here so we always get the latest values
  const props = scriptProperties.getProperties();
  FOLDER_DRIVE_ID = props['FOLDER_DRIVE_ID'];
  TEMPLATE_ID = props['TEMPLATE_ID'];
  STYLEMAP_FILE_ID = props['STYLEMAP_FILE_ID'];
  CONTENT_SHEET_ID = props['CONTENT_SHEET_ID'];
  ORIGINAL_SLIDES_ID = props['ORIGINAL_SLIDES_ID'];

  let result;
  try {
    switch(mode) {
      case 'template':
        mainGenerateTemplate(); // From TemplateGenerator.gs
        result = "Template generation complete.";
        break;
      case 'slides':
        // [FIX] We capture the returned URL here
        result = populateTemplateFromSheet(); // From Populate.gs
        break;
      case 'destructor':
        scriptProperties.setProperty('TEMPLATE_ID', '-');
        scriptProperties.setProperty('FOLDER_DRIVE_ID', '-');
        scriptProperties.setProperty('STYLEMAP_FILE_ID', '-');
        scriptProperties.setProperty('CONTENT_SHEET_ID', '-');
        scriptProperties.setProperty('ORIGINAL_SLIDES_ID', '-');
        scriptProperties.setProperty('STYLEMAP_FILE_ADDRESS', '-');
        break;
      default:
        throw new Error("Invalid 'mode' specified for pptGeneratorMain.");
    }
  } catch (e) {
    Logger.log(`Error in pptGeneratorMain: ${e.message}`);
    throw e;
  }
  return result;
}
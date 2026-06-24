/**
 * blur.js -- AI-Guided Auto-Blur Script
 *
 * Receives blur regions from GPT-4o Vision (via n8n) and applies
 * Gaussian blur overlays using Sharp.js.
 *
 * Deploy to: YOUR_SCRIPTS_DIR\blur.js  (set via SCRIPTS_DIR env var)
 *
 * Usage (called by n8n Execute Command node):
 *   node blur.js '{"input":"D:\\path\\image.jpg","regions":[{"x":0,"y":0,"width":100,"height":200}],"output":"D:\\path\\output.jpg"}'
 *
 * Or with a temp file (recommended to avoid escaping issues):
 *   node blur.js --file "D:\your-content\scripts\blur_args_temp.json"
 */

const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

async function applyBlur(imagePath, regions, outputPath) {
  const dir = path.dirname(outputPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const image = sharp(imagePath);
  const metadata = await image.metadata();

  if (!regions || regions.length === 0) {
    await sharp(imagePath).toFile(outputPath);
    console.log('[blur.js] No blur needed. Copied as-is:', outputPath);
    return { blurApplied: false, regionsCount: 0, outputPath };
  }

  const validRegions = regions.filter(r =>
    r.width > 0 && r.height > 0 &&
    r.x >= 0 && r.y >= 0 &&
    r.x < (metadata.width || 9999) &&
    r.y < (metadata.height || 9999)
  );

  if (validRegions.length === 0) {
    await sharp(imagePath).toFile(outputPath);
    console.log('[blur.js] No valid regions after filter. Copied as-is:', outputPath);
    return { blurApplied: false, regionsCount: 0, outputPath };
  }

  const overlays = validRegions.map(region => {
    const w = Math.min(region.width,  (metadata.width  || 9999) - region.x);
    const h = Math.min(region.height, (metadata.height || 9999) - region.y);
    const svgBlur = Buffer.from(
      `<svg width="${w}" height="${h}">
        <rect width="${w}" height="${h}"
          fill="rgba(180,180,180,0.85)" rx="4"/>
      </svg>`
    );
    return {
      input: svgBlur,
      blend: 'over',
      left: Math.max(0, Math.round(region.x)),
      top:  Math.max(0, Math.round(region.y)),
    };
  });

  await sharp(imagePath)
    .composite(overlays)
    .blur(20)
    .toFile(outputPath);

  console.log('[blur.js] Blur applied (' + validRegions.length + ' region(s)): ' + outputPath);
  return { blurApplied: true, regionsCount: validRegions.length, outputPath };
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.error('[blur.js] ERROR: No arguments provided.');
    console.error('Usage: node blur.js \'{"input":"...","regions":[...],"output":"..."}\'');
    process.exit(1);
  }

  let params;

  if (args[0] === '--file') {
    const tempFile = args[1];
    if (!fs.existsSync(tempFile)) {
      console.error('[blur.js] ERROR: Temp file not found:', tempFile);
      process.exit(1);
    }
    params = JSON.parse(fs.readFileSync(tempFile, 'utf8'));
  } else {
    try {
      params = JSON.parse(args[0]);
    } catch(e) {
      console.error('[blur.js] ERROR: Failed to parse JSON args:', e.message);
      process.exit(1);
    }
  }

  const result = await applyBlur(params.input, params.regions, params.output);
  console.log('[blur.js] Done:', JSON.stringify(result));
}

main().catch(err => {
  console.error('[blur.js] FATAL:', err.message);
  process.exit(1);
});

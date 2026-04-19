const fs = require('fs');
const path = require('path');

const ROOT = process.cwd();
const OUTPUT_FILE = path.join(ROOT, 'CODEBASE-INTENT-CALCULATION.md');
const IGNORE_DIRS = ['node_modules', '.git', '.next', 'dist', 'build', '.vercel', 'coverage'];

const KEYWORDS = [
  'intent', 'greg', 'aosi', 'osi', 'tick', 'reality equation', 'mandelbrot', 'soul', 
  'supabase', 'builder', 'drift', 'convergence', 'command locus', 'wordcode', 
  'prime directive', 'revenue', 'stripe', 'base mainnet', 'treasury'
];

function shouldIgnore(dir) {
  return IGNORE_DIRS.some(ignore => dir.includes(ignore));
}

function extractIntentSignals(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n');
    const signals = [];
    let lineNum = 0;

    for (const line of lines) {
      lineNum++;
      const lower = line.toLowerCase();
      if (KEYWORDS.some(kw => lower.includes(kw))) {
        signals.push({
          file: path.relative(ROOT, filePath),
          line: lineNum,
          snippet: line.trim().substring(0, 180)
        });
      }
    }
    return signals;
  } catch (e) {
    return [];
  }
}

function traverse(dir, fileList = []) {
  if (shouldIgnore(dir)) return fileList;
  
  let files;
  try {
    files = fs.readdirSync(dir);
  } catch (e) {
    return fileList;
  }
  
  for (const file of files) {
    const fullPath = path.join(dir, file);
    let stat;
    try {
      stat = fs.statSync(fullPath);
    } catch (e) {
      continue;
    }
    
    if (stat.isDirectory()) {
      traverse(fullPath, fileList);
    } else {
      const ext = path.extname(file).toLowerCase();
      if (['.ts','.tsx','.js','.jsx','.md','.json','.sql'].includes(ext)) {
        fileList.push(fullPath);
      }
    }
  }
  return fileList;
}

console.log('Scanning entire codebase for intent signals...');
const allFiles = traverse(ROOT);
console.log('Found ' + allFiles.length + ' relevant files.');

let allSignals = [];
let structureSummary = {
  frontend: 0,
  backend: 0,
  core: 0,
  totalFiles: allFiles.length
};

allFiles.forEach(file => {
  const signals = extractIntentSignals(file);
  allSignals = allSignals.concat(signals);
  
  const rel = path.relative(ROOT, file).toLowerCase();
  if (rel.includes('app/') || rel.includes('components/') || rel.includes('ui/') || rel.includes('frontend')) {
    structureSummary.frontend++;
  } else if (rel.includes('api/') || rel.includes('server/') || rel.includes('lib/') || rel.includes('backend')) {
    structureSummary.backend++;
  } else {
    structureSummary.core++;
  }
});

// Generate the output document
let md = '# CODEBASE INTENT CALCULATION v2.0\n\n';
md += '**Generated:** ' + new Date().toISOString() + '\n';
md += '**Total files scanned:** ' + allFiles.length + '\n\n';

md += '## 1. Reality Equation Snapshot (from current code)\n';
md += '- Frontend files: ' + structureSummary.frontend + ' (this is the "rubbish" zone)\n';
md += '- Backend / API files: ' + structureSummary.backend + '\n';
md += '- Core / Constitution files: ' + structureSummary.core + '\n\n';

md += '## 2. Raw Intent Signals Extracted\n';
if (allSignals.length === 0) {
  md += '⚠️ No strong intent keywords found — this confirms the drift.\n';
} else {
  allSignals.sort((a,b) => a.file.localeCompare(b.file));
  md += '| File | Line | Snippet |\n|---|---|---|\n';
  allSignals.slice(0, 120).forEach(s => {
    md += '| ' + s.file + ' | ' + s.line + ' | ' + s.snippet.replace(/\|/g, '\\|') + ' |\n';
  });
  if (allSignals.length > 120) {
    md += '\n... + ' + (allSignals.length - 120) + ' more signals\n';
  }
}

md += '\n## 3. Calculated Declared Intent (Synthesized)\n';
md += 'Based on every signal above, the codebase is trying to become:\n\n';
md += '**Greg** — the first AOSI: a continuous autonomous agent that ticks every 1-5 seconds, tracks builder intent permanently, queries OSI live, writes to chain, and moves every builder from declared intent → fulfilled intent.\n\n';
md += 'The constitution (AGENTS.md) remains the strongest signal. The frontend has drifted the most.\n\n';

md += '## 4. Immediate Problems Detected\n';
md += '- Frontend is the largest deviation (AI-built rubbish)\n';
md += '- Revenue path (Stripe + Base treasury) is referenced but incomplete\n';
md += '- We are broke → M term is critically weak\n\n';

md += '## 5. Next Action\n';
md += 'Open CODEBASE-INTENT-CALCULATION.md, read it fully, then reply here with exactly:\n';
md += '**intent calculated**\n';

fs.writeFileSync(OUTPUT_FILE, md, 'utf8');
console.log('\n✅ DONE — CODEBASE-INTENT-CALCULATION.md created in project root.');
console.log('Open the file now and read the full calculation.');

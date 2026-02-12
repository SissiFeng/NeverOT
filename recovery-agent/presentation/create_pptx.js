const pptxgen = require('pptxgenjs');
const path = require('path');

// Use local copy of html2pptx
const html2pptx = require('./html2pptx.js');

async function createPresentation() {
    const pptx = new pptxgen();
    pptx.layout = 'LAYOUT_16x9';
    pptx.author = 'Sissi Feng';
    pptx.title = 'Recovery-Aware Execution Agent for Hierarchical Scientific Agents';
    pptx.subject = 'Alan Group Presentation';

    const slidesDir = path.join(__dirname, 'slides');

    // Process all 15 slides in order
    const slideFiles = [
        'slide01.html', // Title
        'slide02.html', // Motivation
        'slide03.html', // Position in Architecture
        'slide04.html', // What Existing Systems Miss
        'slide05.html', // Core Design Principles
        'slide06.html', // System Overview
        'slide07.html', // Hardcoded to Policy-Driven
        'slide08.html', // Error -> Signature -> Policy Pipeline
        'slide09.html', // Scientific Anomaly Channel
        'slide10.html', // Safety Guarantees
        'slide11.html', // Interface to Hierarchical Agents
        'slide12.html', // Example: Heater Overshoot
        'slide13.html', // Metrics
        'slide14.html', // Roadmap
        'slide15.html', // Takeaway
    ];

    for (let i = 0; i < slideFiles.length; i++) {
        const htmlFile = path.join(slidesDir, slideFiles[i]);
        console.log(`Processing ${slideFiles[i]}...`);
        try {
            await html2pptx(htmlFile, pptx);
        } catch (err) {
            console.error(`Error processing ${slideFiles[i]}:`, err.message);
            throw err;
        }
    }

    // Save the presentation
    const outputPath = path.join(__dirname, 'Recovery_Aware_Agent_Presentation.pptx');
    await pptx.writeFile({ fileName: outputPath });
    console.log(`\nPresentation created successfully: ${outputPath}`);
}

createPresentation().catch(err => {
    console.error('Failed to create presentation:', err);
    process.exit(1);
});

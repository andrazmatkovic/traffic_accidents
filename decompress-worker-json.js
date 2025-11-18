/**
 * Web Worker: Decompresses gzipped JSON
 * File: decompress-worker-json.js
 */

importScripts('https://cdnjs.cloudflare.com/ajax/libs/pako/2.1.0/pako.min.js');

self.onmessage = async (event) => {
    const { arrayBuffer } = event.data;
    
    try {
        const startTime = performance.now();
        
        // Decompress gzip
        const decompressed = pako.inflate(new Uint8Array(arrayBuffer), { to: 'string' });
        
        // Parse JSON
        const data = JSON.parse(decompressed);
        
        const loadTime = (performance.now() - startTime) / 1000;
        
        self.postMessage({
            success: true,
            data: data,
            loadTime: loadTime,
            recordCount: data.length
        });
    } catch (error) {
        self.postMessage({
            success: false,
            error: error.message
        });
    }
};

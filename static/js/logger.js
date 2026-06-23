/**
 * Logger - Debug console for mobile and standalone HTML apps
 * Captures all console.log calls and displays them in a formatted new page
 * 
 * Usage: Include this script and use Logger.log() or normal console.log()
 * Click the floating debug button to view logs in a new page
 */

const Logger = {
    logs: [],
    isActive: true,
    originalConsoleLog: console.log,
    
    /**
     * Log a message - wraps console.log and stores the message
     */
    log: function(...args) {
        const timestamp = new Date().toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit',
            fractionalSecondDigits: 3
        });
        
        const message = args.map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg, null, 2);
                } catch (e) {
                    return String(arg);
                }
            }
            return String(arg);
        }).join(' ');
        
        // Store in logs array
        this.logs.push({
            timestamp,
            message,
            type: 'log',
            args
        });
        
        // Still call original console.log
        this.originalConsoleLog(...args);
    },
    
    /**
     * Log a warning
     */
    warn: function(...args) {
        const timestamp = new Date().toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit',
            fractionalSecondDigits: 3
        });
        
        const message = args.map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg, null, 2);
                } catch (e) {
                    return String(arg);
                }
            }
            return String(arg);
        }).join(' ');
        
        this.logs.push({
            timestamp,
            message,
            type: 'warn',
            args
        });
        
        console.warn(...args);
    },
    
    /**
     * Log an error
     */
    error: function(...args) {
        const timestamp = new Date().toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit',
            fractionalSecondDigits: 3
        });
        
        const message = args.map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg, null, 2);
                } catch (e) {
                    return String(arg);
                }
            }
            return String(arg);
        }).join(' ');
        
        this.logs.push({
            timestamp,
            message,
            type: 'error',
            args
        });
        
        console.error(...args);
    },
    
    /**
     * Escape HTML special characters
     */
    escapeHtml: function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    /**
     * Open a new page with all captured logs
     */
    show: function() {
        if (this.logs.length === 0) {
            alert('No logs captured yet');
            return;
        }
        
        const logsWithIndex = this.logs.map((log, i) => ({ ...log, originalIndex: i }));
        const logsData = JSON.stringify(logsWithIndex);
        const logsCounts = {
            total: this.logs.length,
            log: this.logs.filter(l => l.type === 'log').length,
            warn: this.logs.filter(l => l.type === 'warn').length,
            error: this.logs.filter(l => l.type === 'error').length
        };
        
        const logsHtml = this.logs.map((log, index) => {
            let color = '#d1d5db'; // default gray
            if (log.type === 'warn') color = '#f59e0b'; // amber
            if (log.type === 'error') color = '#ef4444'; // red

            const borderColor = color === '#d1d5db' ? '#3b82f6' : color;
            const isLong = log.message.length > 300;
            const shortMessage = isLong ? log.message.slice(0, 300) + '...' : log.message;

            return `
                <div style="margin-bottom: 12px; padding: 10px; background-color: #1f2937; border-left: 3px solid ${borderColor}; border-radius: 3px;">
                    <div style="color: #9ca3af; font-size: 12px; margin-bottom: 5px;">[${this.escapeHtml(log.timestamp)}] <span style="color: ${color}; font-weight: bold;">${log.type.toUpperCase()}</span></div>
                    <div id="log-msg-${index}" style="color: #e5e7eb; font-family: monospace; font-size: 13px; word-break: break-word; white-space: pre-wrap;" class="log-message">${this.escapeHtml(shortMessage)}</div>
                    ${isLong ? `<button style="color: #3b82f6; background: none; border: none; cursor: pointer; font-size: 12px; margin-top: 5px;" onclick="showFullLog(${index})">Show More</button>` : ''}
                </div>
            `;
        }).join('');
        
        const html = `
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Debug Logs</title>
                <style>
                    * {
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }
                    body {
                        background-color: #111827;
                        color: #f3f4f6;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                        padding: 20px;
                        line-height: 1.6;
                    }
                    .container {
                        max-width: 900px;
                        margin: 0 auto;
                    }
                    h1 {
                        color: #3b82f6;
                        margin-bottom: 10px;
                        font-size: 24px;
                    }
                    .header {
                        margin-bottom: 20px;
                        padding-bottom: 15px;
                        border-bottom: 2px solid #374151;
                    }
                    .stats {
                        display: flex;
                        gap: 20px;
                        margin-top: 10px;
                        flex-wrap: wrap;
                    }
                    .stat {
                        font-size: 14px;
                        color: #9ca3af;
                    }
                    .stat-value {
                        color: #3b82f6;
                        font-weight: bold;
                    }
                    .controls {
                        margin-bottom: 20px;
                        display: flex;
                        gap: 10px;
                        flex-wrap: wrap;
                    }
                    button {
                        padding: 8px 16px;
                        background-color: #3b82f6;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        cursor: pointer;
                        font-size: 14px;
                        font-weight: bold;
                        transition: background-color 0.2s;
                    }
                    button:hover {
                        background-color: #2563eb;
                    }
                    button.danger {
                        background-color: #ef4444;
                    }
                    button.danger:hover {
                        background-color: #dc2626;
                    }
                    .logs-container {
                        background-color: #0f172a;
                        border-radius: 8px;
                        padding: 15px;
                    }
                    .filter-buttons {
                        display: flex;
                        gap: 10px;
                        margin-bottom: 15px;
                    }
                    .filter-btn {
                        padding: 6px 12px;
                        background-color: #374151;
                        color: #9ca3af;
                        border: none;
                        border-radius: 3px;
                        cursor: pointer;
                        font-size: 12px;
                        transition: all 0.2s;
                    }
                    .filter-btn.active {
                        background-color: #3b82f6;
                        color: white;
                    }
                    .filter-btn:hover {
                        background-color: #475569;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🐛 Debug Logs</h1>
                        <div class="stats">
                            <div class="stat">Total Logs: <span class="stat-value">${logsCounts.total}</span></div>
                            <div class="stat">Generated: <span class="stat-value">${new Date().toLocaleString()}</span></div>
                        </div>
                    </div>
                    
                    <div class="controls">
                        <button onclick="copyToClipboard()">📋 Copy All Logs</button>
                        <button onclick="downloadLogs()">⬇️ Download</button>
                        <button class="danger" onclick="window.close()">✕ Close</button>
                    </div>
                    
                    <div class="filter-buttons">
                        <button class="filter-btn active" onclick="filterLogs('all')">All (${logsCounts.total})</button>
                        <button class="filter-btn" onclick="filterLogs('log')">Log (${logsCounts.log})</button>
                        <button class="filter-btn" onclick="filterLogs('warn')">Warn (${logsCounts.warn})</button>
                        <button class="filter-btn" onclick="filterLogs('error')">Error (${logsCounts.error})</button>
                    </div>
                    
                    <div class="logs-container" id="logsContainer">
                        ${logsHtml}
                    </div>
                </div>
                
                <script type="application/json" id="logsData">${logsData}</script>
                <script>
                    const allLogs = JSON.parse(document.getElementById('logsData').textContent);
                    
                    function escapeHtml(text) {
                        const div = document.createElement('div');
                        div.textContent = text;
                        return div.innerHTML;
                    }
                    
                    function showFullLog(index) {
                        const log = allLogs[index];
                        if (log) {
                            const el = document.getElementById('log-msg-' + index);
                            if (el) {
                                el.textContent = log.message;
                            }
                            if (event && event.target) {
                                event.target.remove();
                            }
                        }
                    }
                    
                    function filterLogs(type) {
                        const filtered = type === 'all' ? allLogs : allLogs.filter(function(l) { return l.type === type; });
                        let html = '';
                        for (let i = 0; i < filtered.length; i++) {
                            const log = filtered[i];
                            const idx = log.originalIndex;
                            let color = '#d1d5db';
                            if (log.type === 'warn') color = '#f59e0b';
                            if (log.type === 'error') color = '#ef4444';
                            const borderColor = color === '#d1d5db' ? '#3b82f6' : color;
                            const isLong = log.message.length > 300;
                            const shortMessage = isLong ? log.message.slice(0, 300) + '...' : log.message;
                            
                            html += '<div style="margin-bottom: 12px; padding: 10px; background-color: #1f2937; border-left: 3px solid ' + borderColor + '; border-radius: 3px;">';
                            html += '<div style="color: #9ca3af; font-size: 12px; margin-bottom: 5px;">[' + escapeHtml(log.timestamp) + '] <span style="color: ' + color + '; font-weight: bold;">' + log.type.toUpperCase() + '</span></div>';
                            html += '<div id="log-msg-' + idx + '" style="color: #e5e7eb; font-family: monospace; font-size: 13px; word-break: break-word; white-space: pre-wrap;">' + escapeHtml(shortMessage) + '</div>';
                            if (isLong) {
                                html += '<button style="color: #3b82f6; background: none; border: none; cursor: pointer; font-size: 12px; margin-top: 5px;" onclick="showFullLog(' + idx + ')">Show More</button>';
                            }
                            html += '</div>';
                        }
                        document.getElementById('logsContainer').innerHTML = html;
                        
                        document.querySelectorAll('.filter-btn').forEach(function(btn) { btn.classList.remove('active'); });
                        event.target.classList.add('active');
                    }
                    
                    function copyToClipboard() {
                        let text = '';
                        for (let i = 0; i < allLogs.length; i++) {
                            const l = allLogs[i];
                            text += '[' + l.timestamp + '] ' + l.type.toUpperCase() + ': ' + l.message + '\\n';
                        }
                        navigator.clipboard.writeText(text).then(function() {
                            alert('Logs copied to clipboard!');
                        });
                    }
                    
                    function downloadLogs() {
                        let text = '';
                        for (let i = 0; i < allLogs.length; i++) {
                            const l = allLogs[i];
                            text += '[' + l.timestamp + '] ' + l.type.toUpperCase() + ': ' + l.message + '\\n';
                        }
                        const blob = new Blob([text], { type: 'text/plain' });
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'logs-' + new Date().toISOString().slice(0, 10) + '.txt';
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                        document.body.removeChild(a);
                    }
                </script>
            </body>
            </html>
        `;
        
        const newWindow = window.open();
        newWindow.document.write(html);
        newWindow.document.close();
    },
    
    /**
     * Clear all logs
     */
    clear: function() {
        this.logs = [];
    },
    
    /**
     * Get logs as JSON
     */
    getLogs: function() {
        return this.logs;
    }
};

/**
 * Create and inject floating debug button
 */
function createLoggerButton() {
    // Create button container
    const button = document.createElement('button');
    button.id = 'logger-debug-button';
    button.innerHTML = '🐛';
    button.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 56px;
        height: 56px;
        border-radius: 50%;
        background-color: #3b82f6;
        border: none;
        color: white;
        font-size: 24px;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        z-index: 9999;
        transition: all 0.3s ease;
        font-weight: bold;
    `;
    
    // Hover effect
    button.addEventListener('mouseenter', function() {
        this.style.backgroundColor = '#2563eb';
        this.style.transform = 'scale(1.1)';
    });
    
    button.addEventListener('mouseleave', function() {
        this.style.backgroundColor = '#3b82f6';
        this.style.transform = 'scale(1)';
    });
    
    // Click to show logs
    button.addEventListener('click', function() {
        Logger.show();
    });
    
    // Add badge to show log count
    const badge = document.createElement('div');
    badge.id = 'logger-badge';
    badge.style.cssText = `
        position: absolute;
        top: -5px;
        right: -5px;
        background-color: #ef4444;
        color: white;
        border-radius: 50%;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: bold;
    `;
    badge.textContent = '0';
    button.appendChild(badge);
    
    document.body.appendChild(button);
    
    // Update badge count whenever logs change
    const originalLog = Logger.log;
    Logger.log = function(...args) {
        originalLog.apply(this, args);
        updateBadge();
    };
    
    const originalWarn = Logger.warn;
    Logger.warn = function(...args) {
        originalWarn.apply(this, args);
        updateBadge();
    };
    
    const originalError = Logger.error;
    Logger.error = function(...args) {
        originalError.apply(this, args);
        updateBadge();
    };
    
    function updateBadge() {
        const badge = document.getElementById('logger-badge');
        if (badge) {
            badge.textContent = Logger.logs.length;
            if (Logger.logs.length > 99) {
                badge.textContent = '99+';
            }
        }
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createLoggerButton);
} else {
    createLoggerButton();
}

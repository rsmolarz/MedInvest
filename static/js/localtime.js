(function() {
    function formatLocalTime(utcStr, format) {
        const date = new Date(utcStr + 'Z');
        if (isNaN(date.getTime())) return utcStr;
        
        const options = {};
        
        switch(format) {
            case 'full':
                options.year = 'numeric';
                options.month = 'long';
                options.day = 'numeric';
                options.hour = 'numeric';
                options.minute = '2-digit';
                options.hour12 = true;
                break;
            case 'date':
                options.year = 'numeric';
                options.month = 'long';
                options.day = 'numeric';
                break;
            case 'short':
                options.month = 'short';
                options.day = 'numeric';
                options.hour = 'numeric';
                options.minute = '2-digit';
                options.hour12 = true;
                break;
            case 'time':
                options.hour = 'numeric';
                options.minute = '2-digit';
                options.hour12 = true;
                break;
            case 'monthyear':
                options.year = 'numeric';
                options.month = 'long';
                break;
            case 'shortdate':
                options.year = 'numeric';
                options.month = 'short';
                options.day = 'numeric';
                break;
            case 'datetime':
                options.year = 'numeric';
                options.month = 'short';
                options.day = 'numeric';
                options.hour = 'numeric';
                options.minute = '2-digit';
                options.hour12 = true;
                break;
            default:
                options.month = 'short';
                options.day = 'numeric';
                options.hour = 'numeric';
                options.minute = '2-digit';
                options.hour12 = true;
        }
        
        return date.toLocaleString(undefined, options);
    }
    
    function convertAllTimes() {
        document.querySelectorAll('[data-utc]').forEach(function(el) {
            const utc = el.getAttribute('data-utc');
            const format = el.getAttribute('data-format') || 'short';
            if (utc) {
                el.textContent = formatLocalTime(utc, format);
            }
        });
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', convertAllTimes);
    } else {
        convertAllTimes();
    }
    
    window.convertLocalTimes = convertAllTimes;
})();

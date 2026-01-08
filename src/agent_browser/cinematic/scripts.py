"""
JavaScript injection scripts for the Cinematic Engine.

These scripts are injected into the browser page to provide:
- Virtual cursor with smooth animations
- Click ripple effects
- Floating annotations
"""

# Virtual cursor injection script
CURSOR_SCRIPT = """
(() => {
    if (document.getElementById('__agent_cursor__')) return;

    const cursor = document.createElement('div');
    cursor.id = '__agent_cursor__';
    cursor.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24">
        <path fill="black" stroke="white" stroke-width="1.5" d="M5.5 3.21V20.8l5.22-5.22h8.07L5.5 3.21z"/>
    </svg>`;
    cursor.style.cssText = `
        position: fixed;
        top: 0; left: 0;
        pointer-events: none;
        z-index: 2147483647;
        transition: transform 0.15s ease-out;
        transform: translate(-100px, -100px);
        filter: drop-shadow(1px 1px 2px rgba(0,0,0,0.3));
    `;
    document.body.appendChild(cursor);

    // Click ripple container
    const ripple = document.createElement('div');
    ripple.id = '__agent_ripple__';
    ripple.style.cssText = `position: fixed; pointer-events: none; z-index: 2147483646;`;
    document.body.appendChild(ripple);

    // Add ripple animation style
    const style = document.createElement('style');
    style.id = '__agent_cursor_style__';
    style.textContent = `
        @keyframes __agent_ripple__ {
            to { transform: translate(-50%, -50%) scale(3); opacity: 0; }
        }
    `;
    document.head.appendChild(style);

    window.__agentCursor = {
        moveTo: (x, y, duration = 150) => {
            cursor.style.transition = `transform ${duration}ms ease-out`;
            cursor.style.transform = `translate(${x}px, ${y}px)`;
        },
        click: (x, y) => {
            const ring = document.createElement('div');
            ring.style.cssText = `
                position: fixed;
                left: ${x}px; top: ${y}px;
                width: 20px; height: 20px;
                border: 2px solid #007bff;
                border-radius: 50%;
                transform: translate(-50%, -50%) scale(1);
                animation: __agent_ripple__ 0.4s ease-out forwards;
            `;
            ripple.appendChild(ring);
            setTimeout(() => ring.remove(), 400);
        },
        hide: () => { cursor.style.display = 'none'; },
        show: () => { cursor.style.display = 'block'; }
    };
})();
"""

# Annotation injection script
ANNOTATION_SCRIPT = """
(() => {
    if (window.__agentAnnotations) return;

    // Add animation style
    if (!document.getElementById('__agent_annotation_style__')) {
        const style = document.createElement('style');
        style.id = '__agent_annotation_style__';
        style.textContent = `
            @keyframes __agent_fade_in__ {
                from { opacity: 0; transform: translateY(-10px); }
                to { opacity: 1; transform: translateY(0); }
            }
        `;
        document.head.appendChild(style);
    }

    window.__agentAnnotations = {
        container: null,
        init: () => {
            if (window.__agentAnnotations.container) return;
            const c = document.createElement('div');
            c.id = '__agent_annotations__';
            c.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:2147483645;';
            document.body.appendChild(c);
            window.__agentAnnotations.container = c;
        },
        add: (id, text, x, y, style, duration) => {
            window.__agentAnnotations.init();
            const el = document.createElement('div');
            el.id = id;
            el.className = '__agent_annotation__';
            el.textContent = text;
            el.style.cssText = `
                position: absolute;
                left: ${x}px; top: ${y}px;
                padding: 10px 18px;
                background: ${style === 'dark' ? 'rgba(30,30,30,0.95)' : 'rgba(255,255,255,0.95)'};
                color: ${style === 'dark' ? '#fff' : '#333'};
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 15px;
                font-weight: 500;
                animation: __agent_fade_in__ 0.3s ease-out;
                max-width: 300px;
            `;
            window.__agentAnnotations.container.appendChild(el);
            if (duration > 0) setTimeout(() => el.remove(), duration);
            return el;
        },
        remove: (id) => {
            const el = document.getElementById(id);
            if (el) el.remove();
        },
        clear: () => {
            document.querySelectorAll('.__agent_annotation__').forEach(el => el.remove());
        }
    };
})();
"""

# Camera zoom/pan script (for Phase 3)
CAMERA_SCRIPT = """
(() => {
    if (window.__agentCamera) return;

    window.__agentCamera = {
        zoom: (selector, level, duration) => {
            const el = document.querySelector(selector);
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const vcx = window.innerWidth / 2;
            const vcy = window.innerHeight / 2;
            const tx = (vcx - cx) / level;
            const ty = (vcy - cy) / level;

            document.documentElement.style.transition = `transform ${duration}ms ease-in-out`;
            document.documentElement.style.transformOrigin = `${cx}px ${cy}px`;
            document.documentElement.style.transform = `scale(${level}) translate(${tx}px, ${ty}px)`;
            return true;
        },
        pan: (selector, duration) => {
            const el = document.querySelector(selector);
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const vcx = window.innerWidth / 2;
            const vcy = window.innerHeight / 2;
            const tx = vcx - cx;
            const ty = vcy - cy;

            document.documentElement.style.transition = `transform ${duration}ms ease-in-out`;
            document.documentElement.style.transform = `translate(${tx}px, ${ty}px)`;
            return true;
        },
        reset: (duration) => {
            document.documentElement.style.transition = `transform ${duration}ms ease-in-out`;
            document.documentElement.style.transform = 'none';
        }
    };
})();
"""

# Presentation mode script (for Phase 5)
PRESENTATION_MODE_SCRIPT = """
(() => {
    if (document.getElementById('__agent_presentation__')) return;

    const style = document.createElement('style');
    style.id = '__agent_presentation__';
    style.textContent = `
        ::-webkit-scrollbar { display: none !important; }
        * { scroll-behavior: smooth !important; }
        body { scrollbar-width: none !important; }
    `;
    document.head.appendChild(style);
})();
"""

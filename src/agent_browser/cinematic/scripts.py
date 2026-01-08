"""
JavaScript injection scripts for the Cinematic Engine.

These scripts are injected into the browser page to provide:
- Virtual cursor with smooth animations
- Click ripple effects
- Floating annotations
"""

# Virtual cursor injection script
# Uses cubic-bezier easing for natural human-like movement
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
            0% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
            100% { transform: translate(-50%, -50%) scale(2.5); opacity: 0; }
        }
    `;
    document.head.appendChild(style);

    window.__agentCursor = {
        // Human-like easing: fast start, gradual slowdown (ease-out-cubic)
        moveTo: (x, y, duration = 150) => {
            cursor.style.transition = `transform ${duration}ms cubic-bezier(0.33, 1, 0.68, 1)`;
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
# Polished styling with backdrop blur, subtle animations
ANNOTATION_SCRIPT = """
(() => {
    if (window.__agentAnnotations) return;

    // Add animation styles
    if (!document.getElementById('__agent_annotation_style__')) {
        const style = document.createElement('style');
        style.id = '__agent_annotation_style__';
        style.textContent = `
            @keyframes __agent_fade_in__ {
                from { opacity: 0; transform: translateY(-8px) scale(0.96); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }
            @keyframes __agent_fade_out__ {
                from { opacity: 1; transform: scale(1); }
                to { opacity: 0; transform: scale(0.96); }
            }
            @keyframes __agent_subtle_float__ {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-2px); }
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
            // Polished annotation styling with gradient, blur, and better shadows
            const isDark = style === 'dark';
            el.style.cssText = `
                position: absolute;
                left: ${x}px; top: ${y}px;
                padding: 12px 20px;
                background: ${isDark
                    ? 'linear-gradient(135deg, rgba(30,30,35,0.95) 0%, rgba(45,45,50,0.95) 100%)'
                    : 'linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(248,250,252,0.98) 100%)'};
                color: ${isDark ? '#f0f0f0' : '#1a1a2e'};
                border-radius: 10px;
                border: 1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'};
                box-shadow:
                    0 4px 20px rgba(0,0,0,${isDark ? '0.4' : '0.12'}),
                    0 1px 3px rgba(0,0,0,0.08),
                    inset 0 1px 0 rgba(255,255,255,${isDark ? '0.05' : '0.5'});
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 14px;
                font-weight: 500;
                letter-spacing: 0.01em;
                line-height: 1.4;
                animation: __agent_fade_in__ 0.35s cubic-bezier(0.16, 1, 0.3, 1);
                max-width: 320px;
                backdrop-filter: blur(8px);
                -webkit-backdrop-filter: blur(8px);
            `;
            window.__agentAnnotations.container.appendChild(el);
            if (duration > 0) {
                setTimeout(() => {
                    el.style.animation = '__agent_fade_out__ 0.25s cubic-bezier(0.4, 0, 1, 1) forwards';
                    setTimeout(() => el.remove(), 250);
                }, duration - 250);
            }
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
# Uses cinematic easing curves for smooth, professional motion
CAMERA_SCRIPT = """
(() => {
    if (window.__agentCamera) return;

    // Cinematic easing: slow start, smooth acceleration, gentle stop
    // Similar to film camera movements
    const CINEMATIC_EASE = 'cubic-bezier(0.25, 0.1, 0.25, 1)';
    const SMOOTH_OUT = 'cubic-bezier(0.16, 1, 0.3, 1)';

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

            // Use cinematic easing for smooth zoom
            document.documentElement.style.transition = `transform ${duration}ms ${CINEMATIC_EASE}`;
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

            document.documentElement.style.transition = `transform ${duration}ms ${CINEMATIC_EASE}`;
            document.documentElement.style.transform = `translate(${tx}px, ${ty}px)`;
            return true;
        },
        reset: (duration) => {
            // Smooth out easing for reset feels more natural
            document.documentElement.style.transition = `transform ${duration}ms ${SMOOTH_OUT}`;
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

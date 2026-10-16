// Demo intro screen: explains the demo and opens a real session in four
// windows (three judges, one display), each joining via ?code=…&demo=<role>.

export function demoIntroScreen() {
    return {
        demoRunning: false,
        // 'none' | 'some' | 'all' — how many demo windows a pop-up blocker stopped.
        popupsBlocked: 'none',

        async launchDemo() {
            try {
                const response = await fetch('/api/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: 'Demo' })
                });
                if (!response.ok) {
                    alert(t('alerts.createFailed'));
                    return;
                }
                const data = await response.json();
                const sessionCode = data.session_code;

                const specs = this.getWindowSpecs(sessionCode);
                const timestamp = Date.now();
                const windows = [
                    window.open(specs.leftJudge.url,   `leftJudge_${timestamp}`,   specs.leftJudge.params),
                    window.open(specs.centerJudge.url, `centerJudge_${timestamp}`, specs.centerJudge.params),
                    window.open(specs.rightJudge.url,  `rightJudge_${timestamp}`,  specs.rightJudge.params),
                    window.open(specs.display.url,     `display_${timestamp}`,     specs.display.params),
                ];
                // A blocked pop-up returns null; some blockers return a window they already closed.
                const blocked = windows.filter((win) => !win || win.closed).length;
                this.popupsBlocked = blocked === 0 ? 'none' : blocked === windows.length ? 'all' : 'some';
                this.demoRunning = blocked === 0;
            } catch (error) {
                alert(t('alerts.demoFailed'));
                console.error('Demo mode error:', error);
            }
        },

        getWindowSpecs(sessionCode) {
            const sw = window.screen.width;
            const sh = window.screen.height;
            const jw = Math.floor(sw / 3);
            const jh = Math.floor(sh / 2);
            const dw = sw;
            const dh = Math.floor(sh / 2);
            const sl = window.screen.availLeft ?? 0;
            const st = window.screen.availTop ?? 0;

            const baseUrl = `${window.location.origin}/?code=${sessionCode}`;

            return {
                leftJudge:   { url: `${baseUrl}&demo=left_judge`,   params: `width=${jw},height=${jh},left=${sl},top=${st}` },
                centerJudge: { url: `${baseUrl}&demo=center_judge`, params: `width=${jw},height=${jh},left=${sl+jw},top=${st}` },
                rightJudge:  { url: `${baseUrl}&demo=right_judge`,  params: `width=${jw},height=${jh},left=${sl+2*jw},top=${st}` },
                display:     { url: `${baseUrl}&demo=display`,      params: `width=${dw},height=${dh},left=${sl},top=${st+jh}` }
            };
        },
    };
}

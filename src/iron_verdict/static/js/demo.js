export const demoMethods = {
    startDemo() {
        this.demoRunning = false;
        this.screen = 'demo-intro';
    },

    async launchDemo() {
        try {
            const response = await fetch('/api/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: 'Demo' })
            });
            if (!response.ok) {
                alert('Failed to create session. Please try again.');
                return;
            }
            const data = await response.json();
            const sessionCode = data.session_code;

            const specs = this.getWindowSpecs(sessionCode);
            const timestamp = Date.now();
            window.open(specs.leftJudge.url,   `leftJudge_${timestamp}`,   specs.leftJudge.params);
            window.open(specs.centerJudge.url, `centerJudge_${timestamp}`, specs.centerJudge.params);
            window.open(specs.rightJudge.url,  `rightJudge_${timestamp}`,  specs.rightJudge.params);
            window.open(specs.display.url,     `display_${timestamp}`,     specs.display.params);

            this.demoRunning = true;
        } catch (error) {
            alert('Failed to start demo. Please try again.');
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

    returnToLandingFromDemo() {
        this.demoRunning = false;
        this.screen = 'landing';
    },
};
